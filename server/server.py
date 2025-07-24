import socket
import os
import json

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

        # TODO : filenameはuuidを使って生成する
        filename = 'test1'

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
            state = 'error in upload'
            print(f'error in uploading file :{file_err}')
        else:
            state = 'success'
            print('Finished downloading the file from client.')

    except Exception as e:
        state = str(e)
        print('Error: ' + state)

    finally:
        print("Closing current connection")
        connection.close()