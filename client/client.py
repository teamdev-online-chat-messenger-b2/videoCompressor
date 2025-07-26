import socket
import sys
import os
import json

def protocol_header(json_size, mediatype_size, payload_size):
    return  json_size.to_bytes(2, 'big') + mediatype_size.to_bytes(1,'big') + payload_size.to_bytes(5,'big')

def show_menu():
    menu = {
        1: '動画ファイルの圧縮',
        2: '動画の解像度の変更', 
        3: '動画のアスペクト比の変更',
        4: '動画をオーディオに変換',
        5: '時間範囲での GIF と WEBM の作成'
    }
    
    print('=== 動画処理メニュー ===')
    for key, value in menu.items():
        print(f'{key} {value}')
    print('========================')
    return menu

def get_user_choice(menu):
    while True:
        try:
            action = int(input('メニューから処理を選択してください: '))
            if action in menu:
                return action
            else:
                print('メニュー内の数字を入力して下さい')
        except ValueError:
            print('正しい数字を入力してください')

def main():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        server_address = config['server_address']
        server_port = config['server_port']
        stream_rate = config['stream_rate']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('サーバーに接続します。')

    try:
        sock.connect((server_address, server_port))
    except socket.error as err:
        print(err)
        sys.exit(1)

    try:
        filepath = input('処理対象の動画ファイルパスを入力してください\n')
        
        # ファイル存在チェックを先に行う
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'ファイルが見つかりません: {filepath}')
            
        mediatype = filepath.split('.')[-1]

        menu = show_menu()
        action = get_user_choice(menu)
        req_params = {'action':action}

        # バイナリモードでファイルを読み込む
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            f.seek(0,0)
            if filesize > pow(2,40):
                raise Exception('処理対象の動画ファイルは1TB以下です。')

            # protocol_header()関数を用いてヘッダ情報を作成し、ヘッダとファイル名をサーバに送信します。
            # JSONサイズ（2バイト）、メディアタイプサイズ（1バイト）、ペイロードサイズ（5バイト）
            req_params_size = len(json.dumps(req_params))
            header = protocol_header(req_params_size, len(mediatype), filesize)

            # ヘッダの送信
            sock.send(header)
            # req_params(json)および、メディアタイプ(mp3など)の送信
            sock.send(json.dumps(req_params).encode('utf-8'))
            sock.send(mediatype.encode('utf-8'))

            # 一度に1400バイトずつ読み出し、送信することにより、ファイルを送信します。Readは読み込んだビットを返します
            data = f.read(stream_rate)
            while data:
                print('Sending...')
                sock.send(data)
                data = f.read(stream_rate)
            
            err_response = sock.recv(4096)
            if err_response:
                response_json = err_response.decode('utf-8')
                print('サーバーからのレスポンス:', response_json)
            else:
                print('成功')

    except FileNotFoundError as nofile_err:
        print('処理対象の動画が見つかりません' + str(nofile_err))

    except Exception as e:
        print('エラー: ' + str(e))

    finally:
        print('ソケットを閉じます')
        sock.close()

if __name__ == '__main__':
    main()