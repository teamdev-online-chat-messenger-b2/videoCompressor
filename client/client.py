def get_resolution_choice():
    resolution_choices = {
        1: ("480p", 854, 480),
        2: ("720p", 1280, 720),
        3: ("1080p", 1920, 1080),
        4: ("1440p", 2560, 1440),
        5: ("4K", 3840, 2160)
    }

    print("-------解像度リスト-------")
    for choice, (resolution_name, width, height) in resolution_choices.items():
        print(f"{choice}. {resolution_name} ({width} * {height})")
    print("------------------------")

    while True:
        try:
            user_choice = int(input("お望みの解像度を選択してください: "))
            if user_choice in resolution_choices:
                return resolution_choices[user_choice][1], resolution_choices[user_choice][2]
            else:
                print("１から５の中から選んでください")
        except ValueError:
            print("正しい数字を入力してください")
