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
            'error_code': self.error_code,
            'description': self.description,
            'solution': self.solution
        }
    
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

def main():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        server_address = config['server_address']
        server_port = config['server_port']
        max_storage = config['max_storage']
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        dir_path = BASE_DIR + config['storage_dir']
        stream_rate = config['stream_rate']

    # アドレスファミリ : socket.AF_INET, 通信方式 : SOCK_STREAM = TCP通信（信頼性あり、順番保証、コネクション型）
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((server_address, server_port))
    sock.listen(1)
    print('サーバーが起動します。クライアントからの接続を待ちます。')

    while True:
        connection, client_address = sock.accept()
        error = None
        try:
            print('クライアントから接続します。。')
            header = connection.recv(8)
            json_size = int.from_bytes(header[:2], 'big')
            mediatype_size = int.from_bytes(header[2:3], 'big')
            file_size = int.from_bytes(header[3:], 'big')

            req_params = connection.recv(json_size).decode('utf-8')
            mediatype = connection.recv(mediatype_size).decode('utf-8')

            filename = f'{uuid.uuid4().hex}.{mediatype}'

            # ファイルサイズが0の場合はエラーとして扱う
            if file_size <= 0:
                raise Exception('ファイルサイズが無効です')

            try:
                with open(os.path.join(dir_path, filename),'wb+') as f:
                    # すべてのデータの読み書きが終了するまで、クライアントから読み込まれます
                    while file_size > 0:
                        data = connection.recv(file_size if file_size <= stream_rate else stream_rate)
                        f.write(data)
                        file_size -= len(data)
            except Exception as file_err:
                error = ErrorInfo('1001', 'ファイルアップロード中のエラー:' + str(file_err), '解決しない場合は管理者にお問い合わせください。')
                print(str(file_err))
            else:
                print('ファイルのアップロードが完了しました。')

        except Exception as e:
            error = ErrorInfo('1002', str(e), '解決しない場合は管理者にお問い合わせください。')
            print(str(e))

        finally:
            if error is not None:
                error_json = error.to_json()              
                error_bytes = error_json.encode('utf-8')
                connection.sendall(error_bytes)
            print('コネクションを閉じます')
            connection.close()

if __name__ == '__main__':
    main()