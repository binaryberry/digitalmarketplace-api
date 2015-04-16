from __future__ import absolute_import

from flask import Flask
from flask.ext.bootstrap import Bootstrap
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.fixers import ProxyFix

from config import config
from . import logging


bootstrap = Bootstrap()
db = SQLAlchemy()


def create_app(config_name):
    application = Flask(__name__)
    application.wsgi_app = ProxyFix(application.wsgi_app)
    application.config.from_object(config[config_name])

    config[config_name].init_app(application)

    if not application.debug:
        logging.init_app(application)

    bootstrap.init_app(application)
    db.init_app(application)

    from .main import main as main_blueprint
    application.register_blueprint(main_blueprint)
    from .status import status as status_blueprint
    application.register_blueprint(status_blueprint)
    if config[config_name].ALLOW_EXPLORER:
        from .explorer import explorer as explorer_blueprint
        application.register_blueprint(explorer_blueprint)

    return application
