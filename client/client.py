def get_resolution_choice():
    resolution_choices = {
        1: ("480p", 854, 480),
        2: ("720p", 1280, 720),
        3: ("1080p", 1920, 1080),
        4: ("1440p", 2560, 1440),
        5: ("4K", 3840, 2160)
    }

    print("---Resolution Choises---")
    for choice, (resolution_name, width, height) in resolution_choices.items():
        print(f"{choice}. {resolution_name} ({width} by {height})")
    print("-----------------------")

    while True:
        try:
            user_choice = int(input("Select Resolution: "))
            if user_choice in resolution_choices:
                return resolution_choices[user_choice][1], resolution_choices[user_choice][2]
            else:
                print("Select from 1 to 5")
        except ValueError:
            print("Type a valid number")

def main():
    # call get_resolution_choice in the main logic
    # if action == 2:
    #     width, height = get_resolution_choice()
    #     req_params = {
    #         'action': action,
    #         'width': width,
    #         'height': height
    #     }
