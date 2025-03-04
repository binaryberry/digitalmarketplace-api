import json
import re
import os
import copy
from decimal import Decimal

from flask import abort
from jsonschema import ValidationError, FormatChecker
from jsonschema.validators import validator_for
from datetime import datetime
from dmutils.formats import DATE_FORMAT

MINIMUM_SERVICE_ID_LENGTH = 10
MAXIMUM_SERVICE_ID_LENGTH = 20

JSON_SCHEMAS_PATH = './json_schemas'
SCHEMA_NAMES = [
    'services-g-cloud-4',
    'services-g-cloud-5',
    'services-g-cloud-6-iaas',
    'services-g-cloud-6-saas',
    'services-g-cloud-6-paas',
    'services-g-cloud-6-scs',
    'services-g-cloud-7-iaas',
    'services-g-cloud-7-saas',
    'services-g-cloud-7-paas',
    'services-g-cloud-7-scs',
    'services-digital-outcomes-and-specialists-digital-outcomes',
    'services-digital-outcomes-and-specialists-digital-specialists',
    'services-digital-outcomes-and-specialists-user-research-studios',
    'services-digital-outcomes-and-specialists-user-research-participants',
    'services-update',
    'users',
    'users-auth',
    'suppliers',
    'new-supplier',
    'contact-information',
]
FORMAT_CHECKER = FormatChecker()


def load_schemas(schemas_path, schema_names):
    loaded_schemas = {}
    for schema_name in schema_names:
        schema_path = os.path.join(schemas_path, '{}.json'.format(schema_name))

        with open(schema_path) as f:
            schema = json.load(f)
            validator = validator_for(schema)
            validator.check_schema(schema)
            loaded_schemas[schema_name] = schema
    return loaded_schemas


_SCHEMAS = load_schemas(JSON_SCHEMAS_PATH, SCHEMA_NAMES)


def get_validator(schema_name, enforce_required=True, required_fields=None):
    if required_fields is None:
        required_fields = []
    if enforce_required:
        schema = _SCHEMAS[schema_name]
    else:
        schema = copy.deepcopy(_SCHEMAS[schema_name])
        schema['required'] = [
            field for field in schema.get('required', [])
            if field in required_fields
        ]
        schema.pop('anyOf', None)
    return validator_for(schema)(schema, format_checker=FORMAT_CHECKER)


def validate_updater_json_or_400(submitted_json):
    try:
        get_validator('services-update').validate(submitted_json)
    except ValidationError as e1:
        abort(400, "JSON validation error: {}".format(e1.message))


def validate_user_json_or_400(submitted_json):
    try:
        get_validator('users').validate(submitted_json)
    except ValidationError as e:
        abort(400, "JSON was not a valid format. {}".format(e.message))
    if submitted_json['role'] == 'supplier' \
            and 'supplierId' not in submitted_json:
        abort(400, "No supplier id provided for supplier user")


def validate_user_auth_json_or_400(submitted_json):
    try:
        validates_against_schema('users-auth', submitted_json)
    except ValidationError as e:
        abort(400, "JSON was not a valid format. {}".format(e.message))


def validate_supplier_json_or_400(submitted_json):
    try:
        get_validator('suppliers').validate(submitted_json)
    except ValidationError as e:
        abort(400, "JSON was not a valid format. {}".format(e.message))


def validate_new_supplier_json_or_400(submitted_json):
    try:
        get_validator('new-supplier').validate(submitted_json)
    except ValidationError as e:
        abort(400, "JSON was not a valid format. {}".format(e.message))


def validate_contact_information_json_or_400(submitted_json):
    try:
        get_validator('contact-information').validate(submitted_json)
    except ValidationError as e:
        abort(400, "JSON was not a valid format. {}".format(e.message))


def validates_against_schema(validator_name, submitted_json):
    try:
        get_validator(validator_name).validate(submitted_json)
    except ValidationError:
        return False
    else:
        return True


def get_validation_errors(validator_name, json_data,
                          enforce_required=True,
                          required_fields=None):
    error_map = {}
    validator = get_validator(validator_name, enforce_required,
                              required_fields)
    errors = validator.iter_errors(json_data)
    form_errors = []
    for error in errors:
        if error.path:
            key = error.path[0]
            error_map[key] = _translate_json_schema_error(
                key, error.validator, error.validator_value, error.message
            )
        elif error.validator in ['required', 'dependencies']:
            regex = r'u?\'(\w+)\' is a dependency of u?\'(\w+)\'' if error.validator == 'dependencies' else r'\'(.*)\''
            key = re.search(regex, error.message).group(1)
            error_map[key] = 'answer_required'
        elif error.validator == 'anyOf':
            if error.validator_value[0].get('title'):
                form_errors.append('{}_required'.format(error.validator_value[0].get('title')))
        else:
            form_errors.append(error.message)
    if form_errors:
        error_map['_form'] = form_errors
    error_map.update(min_price_less_than_max_price(error_map, json_data))

    return error_map


def min_price_less_than_max_price(error_map, json_data):

    def return_min_and_max_price_keys(json_data):
        if 'priceMin' in json_data:
            return 'priceMin', 'priceMax'

        specialist_price_keys = [k for k in json_data.keys() if k.endswith(('PriceMin', 'PriceMax'))]
        if specialist_price_keys:
            return \
                next((key for key in specialist_price_keys if key.endswith('PriceMin')), None), \
                next((key for key in specialist_price_keys if key.endswith('PriceMax')), None)

        return None, None

    min_price_key, max_price_key = return_min_and_max_price_keys(json_data)

    if min_price_key:
        if min_price_key in json_data and json_data.get(max_price_key):
            if min_price_key not in error_map and max_price_key not in error_map:
                if Decimal(json_data[min_price_key]) > Decimal(json_data[max_price_key]):
                    return {max_price_key: 'max_less_than_min'}
    return {}


def is_valid_service_id(service_id):
    """
    Validate that service ids contain only letters
    numbers and dashes ([A-z0-9-]) and that they're
    less than | equal to `MINIMUM_SERVICE_ID_LENGTH`
    greater than | equal to `MAXIMUM_SERVICE_ID_LENGTH`
    :param service_id:
    :return True|False:
    """

    return is_valid_string(
        service_id,
        MINIMUM_SERVICE_ID_LENGTH,
        MAXIMUM_SERVICE_ID_LENGTH
    )


def is_valid_service_id_or_400(service_id):
    if is_valid_service_id(service_id):
        return True
    else:
        abort(400, "Invalid service ID supplied: %s" % service_id)


def is_valid_date(date, default_format=DATE_FORMAT):
    try:
        datetime.strptime(date, default_format)
        return True
    except ValueError:
        return False


def is_valid_acknowledged_state(acknowledged):
    return acknowledged in ['all', 'true', 'false']


def is_valid_string_or_400(string):
    if not is_valid_string(string):
        abort(400, "invalid value {}".format(string))


def is_valid_string(string, minlength=1, maxlength=255):
    regex_match_valid_service_id = r"^[A-z0-9-]{%s,%s}$" % (
        minlength,
        maxlength
    )

    if re.search(regex_match_valid_service_id, string):
        return True

    return False


def _translate_json_schema_error(key, validator, validator_value, message):
    validator_type_to_error = {
        'minLength': 'answer_required',
        'minItems': 'answer_required',
        'minimum': 'not_a_number',
        'maximum': 'not_a_number',
        'maxItems': 'under_10_items',
        'maxLength': 'under_character_limit',
    }

    if validator in validator_type_to_error:
        return validator_type_to_error[validator]

    elif validator == 'required':
        if "'assurance'" in message:
            return 'assurance_required'
        else:
            return 'answer_required'

    elif validator == 'pattern':
        # Since error messages are now specified in the manifests, we can (in the future) generalise the returned
        # string and just show the correct message
        if key.endswith(('priceMin', 'priceMax', 'PriceMin', 'PriceMax')):
            return 'not_money_format'

        return 'under_{}_words'.format(_get_word_count(validator_value))

    elif validator == 'enum' and key == 'priceUnit':
        return 'no_unit_specified'

    elif validator == 'type' and validator_value == 'number':
        return 'not_a_number'

    return message


def _get_word_count(message):
    count_minus_one_string = re.search("\{0,(\d+)", message).group(1)
    count_minus_one = int(count_minus_one_string)
    return count_minus_one + 1
