from flask import Blueprint, request, jsonify
from models import Cliente, Inventario, Locacao, ItensLocados, RegistroDanos
from helpers import atualizar_estoque, restaurar_estoque, handle_database_error
from datetime import date
import psycopg2
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Criação do blueprint para as rotas de locação
locacoes_routes = Blueprint('locacoes_routes', __name__, url_prefix='/locacoes')

@locacoes_routes.route('', methods=['GET'])
@locacoes_routes.route('/', methods=['GET'])
def get_locacoes():
    """Rota para listar todas as locações com detalhes do cliente e itens locados."""
    try:
        locacoes = Locacao.get_all_detailed()
        logging.info(f"Locações encontradas: {len(locacoes)}")
        return jsonify(locacoes), 200
    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro inesperado ao buscar locações: {ex}")
        return jsonify({"error": "Erro inesperado ao buscar locações."}), 500

@locacoes_routes.route('/cliente/<int:client_id>', methods=['GET'])
def get_locacoes_por_cliente(client_id):
    """Rota para listar todas as locações de um cliente específico."""
    try:
        locacoes_cliente = Locacao.get_by_client_id(client_id)
        if locacoes_cliente:
            logging.info(f"Locações encontradas para o cliente ID {client_id}: {len(locacoes_cliente)}")
            return jsonify(locacoes_cliente), 200
        else:
            logging.warning(f"Nenhuma locação encontrada para o cliente ID {client_id}.")
            return jsonify([]), 404

    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro ao buscar locações para o cliente ID {client_id}: {ex}")
        return jsonify({"error": "Erro ao buscar locações para o cliente."}), 500

@locacoes_routes.route('/<int:locacao_id>', methods=['GET'])
def get_locacao_detalhes(locacao_id):
    """Rota para obter detalhes específicos de uma locação."""
    try:
        locacao = Locacao.get_detailed_by_id(locacao_id)
        if not locacao:
            return jsonify({"error": "Locação não encontrada"}), 404
        return jsonify(locacao), 200
    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro ao obter detalhes da locação ID {locacao_id}: {ex}")
        return jsonify({"error": "Erro ao buscar detalhes da locação."}), 500

@locacoes_routes.route('/ativos', methods=['GET'])
def get_locacoes_ativas():
    """Rota para listar todas as locações ativas (data_fim >= data atual)."""
    try:
        locacoes_ativas = Locacao.get_active_locacoes()
        logging.info(f"Locações ativas encontradas: {len(locacoes_ativas)}")
        return jsonify(locacoes_ativas), 200
    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro ao buscar locações ativas: {ex}")
        return jsonify({"error": "Erro ao buscar locações ativas."}), 500

@locacoes_routes.route('/alertas', methods=['GET'])
def get_locacoes_com_alertas():
    """Rota para listar locações finalizadas sem devolução registrada."""
    try:
        locacoes_com_alertas = Locacao.get_locacoes_sem_devolucao()
        logging.info(f"Locações com alertas encontradas: {len(locacoes_com_alertas)}")
        return jsonify(locacoes_com_alertas), 200
    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro ao buscar locações com alertas: {ex}")
        return jsonify({"error": "Erro ao buscar locações com alertas."}), 500

@locacoes_routes.route('', methods=['POST'])
@locacoes_routes.route('/', methods=['POST'])
def add_locacao():
    """Rota para adicionar uma nova locação."""
    try:
        nova_locacao = request.get_json()
        logging.info(f"Dados da nova locação recebidos: {nova_locacao}")

        cliente_info = nova_locacao.get('cliente_info', {})
        nome_cliente = cliente_info.get('nome')
        telefone_cliente = cliente_info.get('telefone')

        if not nome_cliente or not telefone_cliente:
            logging.warning("Nome e telefone do cliente são obrigatórios!")
            return jsonify({"error": "Nome e telefone do cliente são obrigatórios!"}), 400

        cliente_id = Cliente.create(
            nome_cliente, 
            cliente_info.get('endereco'), 
            telefone_cliente, 
            cliente_info.get('referencia')
        )
        if cliente_id is None:
            logging.error("Erro ao criar o cliente")
            return jsonify({"error": "Erro ao criar o cliente"}), 500

        logging.info(f"Cliente criado com sucesso: ID {cliente_id}")

        itens_locados = nova_locacao.get('itens', [])
        if not nova_locacao.get('data_inicio') or not nova_locacao.get('data_fim') or nova_locacao.get('valor_total') is None or not itens_locados:
            logging.warning("Todos os campos da locação e itens são obrigatórios!")
            return jsonify({"error": "Todos os campos da locação e itens são obrigatórios!"}), 400

        locacao_id = Locacao.create(
            cliente_id, 
            nova_locacao['data_inicio'], 
            nova_locacao['data_fim'], 
            nova_locacao['valor_total'],
            status="ativo"
        )
        if locacao_id is None:
            logging.error("Erro ao criar a locação!")
            return jsonify({"error": "Erro ao criar a locação!"}), 500

        logging.info(f"Locação criada com sucesso: ID {locacao_id}")

        for item in itens_locados:
            modelo_item = item.get('modelo')
            quantidade = item.get('quantidade')

            if not modelo_item or quantidade is None or quantidade <= 0:
                logging.warning("Modelo e quantidade do item são obrigatórios e a quantidade deve ser positiva.")
                return jsonify({"error": "Modelo e quantidade do item são obrigatórios!"}), 400

            item_id = Inventario.get_item_id_by_modelo(modelo_item)
            if item_id is None:
                logging.warning(f"Item não encontrado no inventário: {modelo_item}")
                return jsonify({"error": f"Item não encontrado no inventário: {modelo_item}"}), 400

            ItensLocados.add_item(locacao_id, item_id, quantidade)
            atualizar_estoque(item_id, quantidade)
            logging.info(f"Item {modelo_item} adicionado à locação ID {locacao_id} e estoque atualizado.")

        logging.info("Locação adicionada com sucesso!")
        return jsonify({"message": "Locação adicionada com sucesso!"}), 201

    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro inesperado ao adicionar locação: {ex}")
        return jsonify({"error": "Erro inesperado ao adicionar locação."}), 500

@locacoes_routes.route('/<int:locacao_id>/confirmar-devolucao', methods=['PATCH'])
def confirmar_devolucao(locacao_id):
    """Rota para confirmar a devolução e atualizar o status da locação para 'concluído'."""
    try:
        dados = request.get_json(silent=True)
        nova_data_fim = dados.get('nova_data_fim') if dados else None
        novo_valor_final = dados.get('novo_valor_final') if dados else None

        if nova_data_fim and novo_valor_final is not None:
            resultado = Locacao.finalizar_antecipadamente(locacao_id, nova_data_fim, novo_valor_final)
            if resultado:
                logging.info(f"Locação ID {locacao_id} finalizada antecipadamente.")
                return jsonify({"message": "Devolução antecipada confirmada com sucesso e status atualizado!"}), 200
            else:
                logging.warning(f"Locação ID {locacao_id} não encontrada para devolução antecipada.")
                return jsonify({"error": "Erro ao finalizar antecipadamente a locação."}), 404
        else:
            logging.info(f"Atualizando o status da locação ID {locacao_id} para 'concluído'.")
            status_atualizado = Locacao.update_status(locacao_id, "concluído")
            if not status_atualizado:
                logging.warning(f"Locação ID {locacao_id} não encontrada.")
                return jsonify({"error": "Locação não encontrada."}), 404

            logging.info(f"Status da locação ID {locacao_id} atualizado para 'concluído'.")
            return jsonify({"message": "Devolução confirmada com sucesso e status atualizado!"}), 200

    except psycopg2.Error as e:
        logging.error(f"Erro no banco de dados ao confirmar devolução para locação ID {locacao_id}: {e}")
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro inesperado ao confirmar devolução para locação ID {locacao_id}: {ex}")
        return jsonify({"error": "Erro ao confirmar devolução.", "detalhe": str(ex)}), 500

@locacoes_routes.route('/<int:locacao_id>/prorrogacao', methods=['PUT'])
def prorrogar_locacao(locacao_id):
    """Rota para prorrogar uma locação existente e atualizar o valor e abatimento, se necessário."""
    try:
        dados = request.get_json()
        dias_adicionais = dados.get('dias_adicionais')
        novo_valor_total = dados.get('novo_valor_total')
        abatimento = dados.get('abatimento', 0)

        if dias_adicionais is None or dias_adicionais <= 0:
            logging.warning("Dias adicionais devem ser positivos!")
            return jsonify({"error": "Dias adicionais devem ser positivos!"}), 400
        if novo_valor_total is None or novo_valor_total <= 0:
            logging.warning("Novo valor total deve ser positivo!")
            return jsonify({"error": "Novo valor total deve ser positivo!"}), 400

        resultado = Locacao.extend(locacao_id, dias_adicionais, novo_valor_total, abatimento)
        
        if resultado:
            logging.info(f"Locação ID {locacao_id} prorrogada e atualizada com sucesso.")
            return jsonify({"message": "Locação prorrogada e atualizada com sucesso!"}), 200
        else:
            logging.warning(f"Locação ID {locacao_id} não encontrada ou erro ao atualizar.")
            return jsonify({"error": "Erro ao prorrogar e atualizar a locação."}), 404

    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro inesperado ao prorrogar e atualizar locação: {ex}")
        return jsonify({"error": "Erro inesperado ao prorrogar e atualizar locação."}), 500

@locacoes_routes.route('/<int:locacao_id>/finalizar_antecipadamente', methods=['PUT'])
def finalizar_antecipadamente(locacao_id):
    """Rota para finalizar uma locação antecipadamente e atualizar data de término e valor final."""
    try:
        dados = request.get_json()
        nova_data_fim = dados.get('nova_data_fim')
        novo_valor_final = dados.get('novo_valor_final')

        if not nova_data_fim or novo_valor_final is None:
            return jsonify({"error": "Nova data de término e novo valor final são obrigatórios!"}), 400

        resultado = Locacao.finalizar_antecipadamente(locacao_id, nova_data_fim, novo_valor_final)

        if resultado:
            logging.info(f"Locação ID {locacao_id} finalizada antecipadamente com sucesso.")
            return jsonify({"message": "Locação finalizada antecipadamente com sucesso!"}), 200
        else:
            logging.warning(f"Locação ID {locacao_id} não encontrada para finalização antecipada.")
            return jsonify({"error": "Locação não encontrada."}), 404

    except psycopg2.Error as e:
        logging.error(f"Erro no banco de dados ao finalizar antecipadamente a locação ID {locacao_id}: {e}")
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro inesperado ao finalizar antecipadamente a locação ID {locacao_id}: {ex}")
        return jsonify({"error": "Erro inesperado ao finalizar antecipadamente a locação."}), 500

@locacoes_routes.route('/<int:locacao_id>/problema', methods=['POST'])
def reportar_problema(locacao_id):
    """Rota para registrar um problema em um item locado."""
    try:
        dados = request.get_json()
        item_id = dados.get('item_id')
        descricao_problema = dados.get('descricao_problema')

        if not item_id or not descricao_problema:
            logging.warning("Item ID e descrição do problema são obrigatórios!")
            return jsonify({"error": "Item ID e descrição do problema são obrigatórios!"}), 400

        RegistroDanos.add_problem(locacao_id, item_id, descricao_problema)
        logging.info(f"Problema registrado para item ID {item_id} na locação ID {locacao_id}.")
        return jsonify({"message": "Problema registrado com sucesso!"}), 200
    except psycopg2.Error as e:
        return handle_database_error(e)
    except Exception as ex:
        logging.error(f"Erro ao registrar problema: {ex}")
        return jsonify({"error": "Erro ao registrar problema."}), 500