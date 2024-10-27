from flask import Blueprint
from .clientes_routes import clientes_routes
from .damages_routes import damages_routes
from .inventario_routes import inventario_routes
from .locacoes_routes import locacoes_routes

main_routes = Blueprint('main_routes', __name__)

main_routes.register_blueprint(clientes_routes, url_prefix='/clientes')
main_routes.register_blueprint(damages_routes, url_prefix='/danos')
main_routes.register_blueprint(inventario_routes, url_prefix='/inventario')
main_routes.register_blueprint(locacoes_routes, url_prefix='/locacoes')
