import socket
import os
import json
import uuid

class ErrorInfo:
    def __init__(self,code, description, solution) -> None:
        self.error_code = code
        self.description = description
        self.solution = solution
    
    def to_dict(self):
        return {
            "error_code": self.error_code,
            "description": self.description,
            "solution": self.solution
        }
    
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    server_address = config['server_address']
    server_port = config['server_port']
    max_storage = config['max_storage']
    # server/server.py から見たプロジェクトルートの絶対パスを取得
    # 必ず "videoCompressor/server/storage" になるようにパスを組み立てる
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dir_path = BASE_DIR + config['storage_dir']
    stream_rate = config['stream_rate']

# アドレスファミリ : socket.AF_INET, 通信方式 : SOCK_STREAM = TCP通信（信頼性あり、順番保証、コネクション型）
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((server_address, server_port))
sock.listen(1)
print('server is starting：waiting from clients')

while True:
    connection, client_address = sock.accept()
    try:
        print(f'connecting from client')
        header = connection.recv(8)
        json_size = int.from_bytes(header[:2], 'big')
        mediatype_size = int.from_bytes(header[2:3], 'big')
        file_size = int.from_bytes(header[3:], 'big')
        print(json_size,mediatype_size, file_size)

        req_params = connection.recv(json_size).decode('utf-8')
        mediatype = connection.recv(mediatype_size).decode('utf-8')
        print(f'request is {req_params}, media type is {mediatype}')

        filename = f"{uuid.uuid4().hex}.{mediatype}"

        # 次に、コードはクライアントから受け取ったファイル名で新しいファイルをフォルダに作成します。このファイルは、withステートメントを使用してバイナリモードで開かれ、write()関数を使用して、クライアントから受信したデータをファイルに書き込みます。データはrecv()関数を使用して塊単位で読み込まれ、データの塊を受信するたびにデータ長がデクリメントされます。
        # w+は終了しない場合はファイルを作成し、そうでない場合はデータを切り捨てます
        try:
            with open(os.path.join(dir_path, filename),'wb+') as f:
                # すべてのデータの読み書きが終了するまで、クライアントから読み込まれます
                while file_size > 0:
                    data = connection.recv(file_size if file_size <= stream_rate else stream_rate)
                    f.write(data)
                    print('recieved {} bytes'.format(len(data)))
                    file_size -= len(data)
                    print(file_size)
        except Exception as file_err:
            error = ErrorInfo('1001', str(file_err), '解決しない場合は管理者にお問い合わせください。')
        else:
            print('ファイルのアップロードが完了しました。')

    except Exception as e:
        error = ErrorInfo('1002', str(file_err), '解決しない場合は管理者にお問い合わせください。')

    finally:
        if error is not None:
            error_json = error.to_json()              
            error_bytes = error_json.encode('utf-8')
            connection.sendall(error_bytes)
        print("コネクションを閉じます")
        connection.close()