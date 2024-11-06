from flask import Flask, render_template, redirect, url_for, request, jsonify
import mercadopago
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:N02r09c95!@localhost/testegit'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

mp = mercadopago.SDK("APP_USR-143259768654594-110601-8f083f022fdc6408ea99c22ec19cfe66-2023785893")

class Transacao(db.Model):
    __tablename__ = 'transacoes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.String(255), nullable=False, unique=True) 
    status = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_type = db.Column(db.String(50), nullable=True)

with app.app_context():
    db.create_all()

produtos = [
    {"id": 1, "nome": "Produto 1", "preco": 20.00},
    {"id": 2, "nome": "Produto 2", "preco": 35.00},
    {"id": 3, "nome": "Produto 3", "preco": 50.00},
    {"id": 4, "nome": "Produto 4", "preco": 70.00}
]

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/produtos')
def produtos_page():
    return render_template("produtos.html", produtos=produtos)

@app.route('/comprar/<int:produto_id>')
def comprar(produto_id):
    produto = next((p for p in produtos if p["id"] == produto_id), None)
    if not produto:
        return "Produto não encontrado.", 404

    try:
    
        preference_data = {
            "items": [{"title": produto["nome"], "quantity": 1, "unit_price": produto["preco"]}],
            "back_urls": {
                "success": url_for("success", _external=True),
                "failure": url_for("failure", _external=True),
                "pending": url_for("pending", _external=True)
            },
            "auto_return": "approved",
            "notification_url": "https://13bd-2804-14d-8e8d-60b6-f4b7-1ec0-7e5e-612d.ngrok-free.app/webhook"
        }

        preference = mp.preference().create(preference_data)
        
        if "response" in preference and "init_point" in preference["response"]:
            mercado_pago_url = preference["response"]["init_point"]
            return redirect(mercado_pago_url)
        else:
            return "Erro ao gerar o link de pagamento.", 500

    except Exception as e:
        return f"Erro ao processar a compra: {e}", 500

@app.route('/success')
def success():
    return render_template("payment_status.html", status="Pagamento aprovado! Obrigado pela compra.")

@app.route('/failure')
def failure():
    return render_template("payment_status.html", status="Pagamento falhou. Tente novamente.")

@app.route('/pending')
def pending():
    return render_template("payment_status.html", status="Pagamento pendente. Aguarde a confirmação.")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        
        data = request.get_json() if request.is_json else request.form.to_dict()
        print("Dados recebidos do webhook:", data)  

        topic = data.get("topic") or request.args.get("topic")
        print("Tópico recebido:", topic)  

        if topic != "payment":
            print("Notificação ignorada: tópico não é 'payment'.")
            return jsonify({"status": "ignored"}), 200

        payment_id = data.get("id") or request.args.get("id") or data.get("data.id")
        print("ID do pagamento recebido:", payment_id) 

        if payment_id:
            
            payment_info = mp.payment().get(payment_id)
            print("Detalhes do pagamento obtidos:", payment_info) 

            if payment_info.get("status") != 200:
                print(f"Erro ao obter detalhes do pagamento: Status {payment_info.get('status')}")
                return jsonify({"status": "error"}), 400

            payment_status = payment_info["response"].get("status")
            payment_type = payment_info["response"].get("payment_type_id")
            amount = payment_info["response"]["transaction_details"].get("total_paid_amount")

            print(f"Dados extraídos - Status: {payment_status}, Amount: {amount}, Payment Type: {payment_type}")  # Log dos dados

            if payment_status and amount is not None:
                
                transacao_existente = Transacao.query.filter_by(payment_id=payment_id).first()
                if not transacao_existente:
                    
                    nova_transacao = Transacao(
                        payment_id=payment_id,
                        status=payment_status,
                        amount=amount,
                        payment_type=payment_type
                    )
                    try:
                        db.session.add(nova_transacao)
                        db.session.commit()
                        print("Transação salva com sucesso no banco de dados!")
                    except Exception as e:
                        print("Erro ao salvar no banco de dados:", repr(e))
                        db.session.rollback()
                else:
                    print("Transação já existente no banco de dados.")
            else:
                print("Dados incompletos na resposta do Mercado Pago.")
        return jsonify({"status": "received"}), 200

    except Exception as e:
        print("Erro ao processar o webhook:", repr(e))
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
