#!/usr/bin/env python
"""Import SSP export files into the API

Usage:
    import_suppliers.py <endpoint> <access_token> <listing_dir> [options]

    --cert=<cert>   Path to certificate file to verify against
    --serial        Do not run in parallel (useful for debugging)
    -v, --verbose   Enable verbose output for errors

Example:
    ./import_suppliers.py --serial http://localhost:5000 myToken ~/myData
"""
from __future__ import print_function
import sys
import os
import json
import requests
import itertools
import multiprocessing
from datetime import datetime

from docopt import docopt


def list_files(directory):
    for root, subdirs, files in os.walk(directory):
        for filename in files:
            yield os.path.abspath(os.path.join(root, filename))

        for subdir in subdirs:
            for subfile in list_files(subdir):
                yield subfile


def print_progress(counter, start_time):
    if counter % 100 == 0:
        time_delta = datetime.now() - start_time
        print("{} in {} ({}/s)".format(counter,
                                       time_delta,
                                       counter / time_delta.total_seconds()))


class SupplierPutter(object):
    def __init__(self, endpoint, access_token, cert=None):
        self.endpoint = endpoint
        self.access_token = access_token
        self.cert = cert

    def __call__(self, file_path):
        with open(file_path) as f:
            try:
                json_from_file = json.load(f)
            except ValueError:
                print("Skipping {}: not a valid JSON file".format(file_path))
                return file_path, None

        response = 400

        for i in json_from_file['suppliers']:
            data = {'suppliers': self.make_supplier_json(i)}
            response = requests.post(
                self.endpoint,
                data=json.dumps(data),
                headers={
                    "content-type": "application/json",
                    "authorization": "Bearer {}".format(self.access_token),
                    },
                verify=self.cert if self.cert else True)

            if response.status_code is not 201:
                print("{0} supplier_id={1}".format(
                    response,
                    i.get('id', None)
                ))

        return file_path, response

    @staticmethod
    def make_supplier_json(json_from_file):
        """
        FROM THIS >>

        {
            "supplierId": 92749,
            "name": "Central Technology Ltd",
            "description": "Daisy is the UK\u2019s largest independent",
            "website": "http://www.ct.co.uk",
            "contactName": "Richard Thompson",
            "contactEmail": "richard.thompson@ct.co.uk",
            "contactPhone": "0845 413 8888",
            "address": {
                "address1": "The Bridge Business Park",
                "address2": null,
                "city": "Chesterfield",
                "country": "United Kingdom",
                "postcode": "GU12 4RQ"
             },
            "dunsNumber": "733053339",
            "eSourcingId": null,
            "clientsString": "Home Office,Metropolitan Police,Aviva"
        }

        TO THIS >>

        {
          "id": 92749,
          "name": "Central Technology Ltd",
          "description": "Daisy is the UK\u2019s largest independent",
          "contactInformation": [
            {
              "website": "http://www.ct.co.uk",
              "contactName": "Richard Thompson",
              "email": "richard.thompson@ct.co.uk",
              "phoneNumber": "0845 413 8888",
              "address1": "The Bridge Business Park",
              "address2": null,
              "city": "Chesterfield",
              "country": "United Kingdom",
              "postcode": "GU12 4RQ"
            }
          ],
          "dunsNumber": "733053339",
          "eSourcingId": null,
          "clients":
          [
            "Home Office",
            "Metropolitan Police",
            "Aviva",
            "ITV",
          ]
        }
        """
        # variable either set to empty string or value of `clientsString` key
        clients_string = '' if 'clientsString' not in json_from_file.keys() \
            else json_from_file['clientsString']

        # `clientsString` list of (comma-separated) clients or empty
        json_from_file['clientsString'] = \
            SupplierPutter.split_comma_separated_value_string_into_list(
                clients_string
            )

        json_from_file = SupplierPutter.change_key_names(
            json_from_file,
            [
                ['clientsString', 'clients'],
                ['contactEmail', 'email'],
                ['contactPhone', 'phoneNumber'],
                ['supplierId', 'id']
            ]
        )

        # key/values nested behind `contactInformation` object
        json_from_file = SupplierPutter.nest_key_value_pairs(
            json_from_file,
            'contactInformation',
            ['email', 'website', 'phoneNumber', 'contactName', 'address']
        )

        # key/values in `address` un-nested (flush with `contactInformation`)
        json_from_file['contactInformation'] = \
            SupplierPutter.un_nest_key_value_pairs(
                json_from_file['contactInformation'],
                'address'
            )

        json_from_file['contactInformation'] = \
            SupplierPutter.convert_a_json_object_into_an_array_with_one_entry(
                json_from_file['contactInformation']
            )

        json_from_file = \
            SupplierPutter.convert_values_to_utf8_except_blacklisted_keys(
                json_from_file,
                ['id', 'clients', 'contactInformation']
            )

        return json_from_file

    @staticmethod
    def convert_values_to_utf8_except_blacklisted_keys(obj, blacklist):
        for key in obj.keys():
            if key not in blacklist:
                obj[key] = SupplierPutter.convert_string_to_utf8(obj[key])

        return obj

    @staticmethod
    def convert_string_to_utf8(string):
        # check if it's a string value
        if isinstance(string, str):
            return unicode(string, 'utf-8')

        else:
            return string

    @staticmethod
    def split_comma_separated_value_string_into_list(string):
        if not string:
            return []

        return [value for value in
                map(unicode.strip, string.split(',')) if len(value) is not 0]

    @staticmethod
    def un_nest_key_value_pairs(obj, key_of_nested_obj):
        if key_of_nested_obj not in obj.keys():
            # abort(400, "No '{0}' key found".format(key_of_nested_obj))
            # TODO: FAIL LOUDLY
            return obj

        nested_obj = obj[key_of_nested_obj]

        obj = drop_foreign_fields(
            obj,
            [key_of_nested_obj]
        )

        for key in nested_obj.keys():
            obj[key] = nested_obj[key]

        return obj

    @staticmethod
    def nest_key_value_pairs(base_obj, key_for_new_obj, keys_to_nest):

        base_obj[key_for_new_obj] = {}

        for key_to_nest in keys_to_nest:
            if key_to_nest in base_obj.keys():
                # Maybe an else if the key isn't here.
                base_obj[key_for_new_obj][key_to_nest] = \
                    base_obj.pop(key_to_nest)

        return base_obj

    @staticmethod
    def change_key_names(obj, list_of_lists_of_key_pairs):

        for key_pair in list_of_lists_of_key_pairs:
            if len(key_pair) is not 2:
                # TODO: FAIL LOUDLY
                return obj

            obj = SupplierPutter.change_key_name(obj, key_pair[0], key_pair[1])

        return obj

    @staticmethod
    def change_key_name(obj, old_key, new_key):
        if old_key in obj.keys():
            obj[new_key] = obj.pop(old_key)

        return obj

    @staticmethod
    def convert_a_json_object_into_an_array_with_one_entry(obj):

        temp = [{}]

        for key in obj.keys():
            temp[0][key] = obj.pop(key)

        obj = temp

        return obj


# TODO this is copied + pasted from app/main/utils.py
def drop_foreign_fields(json_object, list_of_keys):
    json_object = json_object.copy()
    for key in list_of_keys:
        json_object.pop(key, None)

    return json_object


def do_import(base_url, access_token, listing_dir, serial, cert, verbose):
    endpoint = "{}/suppliers".format(base_url)
    print("Base URL: {}".format(base_url))
    print("Access token: {}".format(access_token))
    print("Listing dir: {}".format(listing_dir))

    if serial:
        mapper = itertools.imap
    else:
        pool = multiprocessing.Pool(10)
        mapper = pool.imap

    putter = SupplierPutter(endpoint, access_token, cert)

    counter = 0
    start_time = datetime.now()
    for file_path, response in mapper(putter, list_files(listing_dir)):
        if response is None:
            print("ERROR: {} not imported".format(file_path),
                  file=sys.stderr)
        elif response.status_code / 100 != 2:
            print("ERROR: {} on {}".format(response.status_code, file_path),
                  file=sys.stderr)
            if verbose:
                print(response.text, file=sys.stderr)
        else:
            counter += 1
            print_progress(counter, start_time)

    print_progress(counter, start_time)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    do_import(
        base_url=arguments['<endpoint>'],
        access_token=arguments['<access_token>'],
        listing_dir=arguments['<listing_dir>'],
        serial=arguments['--serial'],
        cert=arguments['--cert'],
        verbose=arguments['--verbose'],
    )
