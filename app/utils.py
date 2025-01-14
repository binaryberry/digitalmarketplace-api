from flask import url_for as base_url_for
from flask import abort, request
from six import iteritems, string_types
from werkzeug.exceptions import BadRequest


def link(rel, href):
    """Generate a link dict from a rel, href pair."""
    if href is not None:
        return {rel: href}


def url_for(*args, **kwargs):
    kwargs.setdefault('_external', True)
    return base_url_for(*args, **kwargs)


def get_valid_page_or_1():
    try:
        return int(request.args.get('page', 1))
    except ValueError:
        abort(400, "Invalid page argument")


def pagination_links(pagination, endpoint, args):
    links = dict()
    if pagination.has_prev:
        links['prev'] = url_for(endpoint, **dict(list(args.items()) + [('page', pagination.prev_num)]))
    if pagination.has_next:
        links['next'] = url_for(endpoint, **dict(list(args.items()) + [('page', pagination.next_num)]))
        links['last'] = url_for(endpoint, **dict(list(args.items()) + [('page', pagination.pages)]))
    return links


def get_json_from_request():
    if request.content_type not in ['application/json',
                                    'application/json; charset=UTF-8']:
        abort(400, "Unexpected Content-Type, expecting 'application/json'")
    try:
        data = request.get_json()
    except BadRequest as e:
        data = None
    if data is None:
        abort(400, "Invalid JSON; must be a valid JSON object")
    return data


def json_has_required_keys(data, keys):
    missing_keys = set(keys) - set(data.keys())
    if missing_keys:
        abort(400, "Invalid JSON must have '%s' keys" % list(missing_keys))


def json_only_has_required_keys(data, keys):
    if set(keys) != set(data.keys()):
        abort(400, "Invalid JSON must only have {} keys".format(keys))


def drop_foreign_fields(json_object, list_of_keys):
    json_object = json_object.copy()
    for key in list_of_keys:
        json_object.pop(key, None)

    return json_object


def json_has_matching_id(data, id):
    if 'id' in data and not id == data['id']:
        abort(400, "id parameter must match id in data")


def display_list(l):
    """Returns a comma-punctuated string for the input list
    with a trailing ('Oxford') comma."""
    length = len(l)
    if length <= 2:
        return " and ".join(l)
    else:
        # oxford comma
        return ", ".join(l[:-1]) + ", and " + l[-1]


def strip_whitespace_from_data(data):
    for key, value in data.items():
        if isinstance(value, list):
            # Strip whitespace and remove empty items from lists
            data[key] = list(
                filter(None, map((lambda x: x.strip()), value))
            )
        elif isinstance(value, string_types):
            # Strip whitespace from strings
            data[key] = value.strip()
    return data


def purge_nulls_from_data(data):
    return dict((k, v) for k, v in iteritems(data) if v is not None)
