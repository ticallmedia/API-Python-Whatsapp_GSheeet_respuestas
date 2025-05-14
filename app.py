from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import http.client

import os
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from dotenv import load_dotenv
load_dotenv()


"""
Proyecto: Creacion API Whatsapp, Funcional con descarga de archivos en Google Sheet

Descripción: Al escribir un mensja por Whatsapp, este se guarda en SQL lite
de RENDER, pero adicionalmente se cargara la ultima fila ingresada en la base
de datos, y se copiara a Google Sheet

Esta version interactua a traves de un menu que pemite elegir la opcion del interes
del usuario.

Se actaliza ling del archivo  LogEnventosTicAllMedia1
https://docs.google.com/spreadsheets/d/1juGRsV5fSs_4LFvAiJNQE8TUMVr8c5KAW-pMaEo6Rh4/edit?usp=drive_link

"""
#________________________________________________________________________________________________________

app = Flask(__name__)

#________________________________________________________________________________________________________
#Base de datos SQLITE
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#Tabla Log
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_y_hora = db.Column(db.DateTime, default = datetime.utcnow)
    telefono = db.Column(db.Text)
    texto = db.Column(db.Text)

#Crear tabla si no existe
with app.app_context():
    db.create_all()

    #prueba1 = Log(texto = 'Mensaje1', telefono='333333')
    #prueba2 = Log(texto = 'Mensaje2', telefono='4444')

    #db.session.add(prueba1)
    #db.session.add(prueba2)
    #db.session.commit()

#________________________________________________________________________________________________________
#funcion para ordendar los registro por fecha y hora

def ordenar_fecha_hora(registros):
    return sorted(registros, key=lambda x: x.fecha_y_hora, reverse=True)


@app.route('/')

def index():
    #obtener todos los registros de la base de  datos
    registros = Log.query.all()
    registros_ordenados = ordenar_fecha_hora(registros)
    return render_template('index.html', registros = registros_ordenados)

#agregar información de la base de datos
mensajes_log = []

#Agregar informacion a la base de datos
#def agregar_mensajes_log(texto,numero):
    #mensajes_log.append(texto,numero)

    #guardar mensajes en la de datos
#   nuevo_registro = Log(texto = texto, telefono=numero)
#    db.session.add(nuevo_registro)
#    db.session.commit()


def agregar_mensajes_log(datos_json):
    datos = json.loads(datos_json)
    texto = datos["mensaje"]
    numero = datos["telefono"]

    nuevo_registro = Log(texto=texto, telefono=numero)
    db.session.add(nuevo_registro)
    db.session.commit()

def exportar_eventos():
    try:
        # Obtener eventos desde SQLAlchemy
        eventos = Log.query.all()

        creds_dict = get_google_credentials_from_env()

        # Configurar acceso a Google Sheets
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]   

        # Convertir el diccionario a un objeto tipo archivo usando json.dumps + StringIO
        from io import StringIO
        json_creds = json.dumps(creds_dict)
        
        # Obtener credenciales desde variables de entorno
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(json_creds), scope)

        # Autenticar con gspread
        client = gspread.authorize(creds)

        # Acceder al Google Sheet
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1juGRsV5fSs_4LFvAiJNQE8TUMVr8c5KAW-pMaEo6Rh4/edit?usp=drive_link').sheet1
        
        #buscar un texto
        titulos = []

        cells = sheet.findall('ID')
        for i in cells:
            titulos.append(i.address)
            
        if not titulos:    
            # Escribir encabezados
            sheet.clear()
            sheet.append_row(["ID", "Fecha", "Teléfono", "Texto"])

            #aplicando formato y color al titulo
            formato = {
                "backgroundColor": {
                    "red": 0.0,
                    "green": 1.0,
                    "blue": 0.0,
                },
                "textFormat" : {"bold": True}

            }
            sheet.format("A1:D1", formato)

        """
        # Escribir todos los datos que existen en la tabla
        for evento in eventos:
            sheet.append_row([
                evento.id,
                evento.fecha_y_hora.strftime('%Y-%m-%d %H:%M:%S'),
                evento.telefono,
                evento.texto
            ])
        """

        # Asegúrate de que la lista no esté vacía
        if eventos:
            ultimo_evento = eventos[-1]
            sheet.append_row([
                ultimo_evento.id,
                ultimo_evento.fecha_y_hora.strftime('%Y-%m-%d %H:%M:%S'),
                ultimo_evento.telefono,
                ultimo_evento.texto
            ])


        return jsonify({'message': 'Eventos exportados exitosamente a Google Sheets'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#credenciales google en variables de entorno
def get_google_credentials_from_env():
    creds_dict = {
        "type": os.environ["GOOGLE_TYPE"],
        "project_id": os.environ["GOOGLE_PROJECT_ID"],
        "private_key_id": os.environ["GOOGLE_PRIVATE_KEY_ID"],
        "private_key": os.environ["GOOGLE_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": os.environ["GOOGLE_CLIENT_EMAIL"],
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "auth_uri": os.environ["GOOGLE_AUTH_URI"],
        "token_uri": os.environ["GOOGLE_TOKEN_URI"],
        "auth_provider_x509_cert_url": os.environ["GOOGLE_AUTH_PROVIDER_CERT_URL"],
        "client_x509_cert_url": os.environ["GOOGLE_CLIENT_CERT_URL"]
    }
    return creds_dict


#________________________________________________________________________________________________________
#creación del TOKEN

TOKEN_TAM = "TAM_CODE_TEST"

@app.route('/webhook', methods = ['GET','POST'])

def webhook():
    if request.method == 'GET':
        challenge = verificar_token(request)
        return challenge
    elif request.method == 'POST':
        reponse = recibir_mensajes(request)
        return reponse
    
def verificar_token(req):
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')

    if challenge and token == TOKEN_TAM:
        return challenge
    else:
        return jsonify({'error': 'Token Invalido'}),401
#________________________________________________________________________________________________________
#recibir mensajes

def recibir_mensajes(req):
    #req = request.get_json()
    #agregar_mensajes_log(req)
    #return jsonify({'message': 'EVENT_RECEIVED'})

    try:
        req = request.get_json()
        entry = req['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        objeto_mensaje = value['messages']

        #identificando el tipo de dato
        if objeto_mensaje:
            messages = objeto_mensaje[0]

            if "type" in messages:
                tipo = messages["type"]

                if tipo == 'interactive':
                    return 0

                if "text" in messages:
                    text = messages["text"]["body"]
                    numero = messages["from"]

                    #agregar_mensajes_log(json.dumps(text,numero))
                    #agregar_mensajes_log(json.dumps(numero))
                    
                    agregar_mensajes_log(json.dumps({"mensaje": text, "telefono": numero}))
                    exportar_eventos()
                    enviar_mensaje_whatsapp(text,numero)


        return jsonify({'message': 'EVENT_RECEIVED'})
    except Exception as e:
        return jsonify({'message': 'EVENT_RECEIVED'})
#________________________________________________________________________________________________________
#Enviar mensajes Whatsapp

def enviar_mensaje_whatsapp(texto,number):
    texto = texto.lower()
    body_mensaje = ""
    numero = 1111111

    if "hola" in texto:
        body_mensaje = "🚀 Hola, ¿Cómo estás? Bienvenido."
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body_mensaje
            }
        }
    else:
        body_mensaje = "📌 Esta interesado en Información de los Servicios."
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body_mensaje
            }
        }

    agregar_mensajes_log(json.dumps({"mensaje": body_mensaje, "telefono": numero}))
    exportar_eventos()    

    #convertir el diccionario a formato json
    data = json.dumps(data)

    #datos de WETA
    headers = {
        "Content-Type" : "application/json",
        "Authorization" : "Bearer EAAUhUBOY4RgBO7o62Ba6z4yWCqsJExT8qGJkrvG8pwB2sunv7sOqAyQmFVbt6x8JagwNj2PncHWGiD9FHhb3oqO5bMZCrLJVMY50LMk6D5ZBqGNswwMXWcVPFjLxbuylZAzZCzc5PzFfjo5OAe4T3wRZASiZBaahL4j0c5zZANmKOFgAlmHCAiVtME81ycVKhaod2WzeZAlVOugoXEVZASuNjwgwuZCr7Xp7dqWBcZD"
    }

    connection = http.client.HTTPSConnection("graph.facebook.com")

    try:
        connection.request("POST","/v22.0/593835203818298/messages", data, headers)
        response = connection.getresponse()
        print(response.status, response.reason)

    except Exception as e:
        agregar_mensajes_log(json.dumps(e))
    
    finally:
        connection.close()

#________________________________________________________________________________________________________

#________________________________________________________________________________________________________

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=80,debug=True)