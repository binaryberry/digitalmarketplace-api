from functools import wraps
from flask import Flask
from flask.ext.bootstrap import Bootstrap
from flask.ext.sqlalchemy import SQLAlchemy
from dmutils import apiclient, init_app, flask_featureflags

from config import configs

bootstrap = Bootstrap()
db = SQLAlchemy()
search_api_client = apiclient.SearchAPIClient()
feature_flags = flask_featureflags.FeatureFlag()


def create_app(config_name):
    application = Flask(__name__)
    application.config['DM_ENVIRONMENT'] = config_name

    init_app(
        application,
        configs[config_name],
        bootstrap=bootstrap,
        db=db,
        feature_flags=feature_flags,
        search_api_client=search_api_client
    )

    from .main import main as main_blueprint
    application.register_blueprint(main_blueprint)
    from .status import status as status_blueprint
    application.register_blueprint(status_blueprint)

    if application.config['ALLOW_EXPLORER']:
        from .explorer import explorer as explorer_blueprint
        application.register_blueprint(explorer_blueprint)

    return application


def isolation_level(level):
    """Return a Flask view decorator to set SQLAlchemy isolation level

    Usage::
        @view("/thingy/<id>", methods=["POST"])
        @isolation_level("SERIALIZABLE")
        def create_thing(id):
            ...
    """
    def decorator(view):
        @wraps(view)
        def view_wrapper(*args, **kwargs):
            if flask_featureflags.is_active('TRANSACTION_ISOLATION'):
                db.session.connection(execution_options={'isolation_level': level})
            return view(*args, **kwargs)
        return view_wrapper
    return decorator
