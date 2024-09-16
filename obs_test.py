import obsws_python as obs


def get_and_enable_item():
    # Define connection parameters
    host = 'localhost'
    port = 4455
    password = 'berm6jSAmWgYe6gv'

    # Create a client instance
    with obs.ReqClient(host=host, port=port, password=password) as client:
        # Get the item ID for 'earth' in the scene 'Scena'
        scene_name = "Scena"
        source_name = "12"
        source_name2 = "clown"
        response = client.get_scene_item_id(scene_name, source_name)
        response2 = client.get_scene_item_list(scene_name)
        group = client.get_scene_item_id(source_name, source_name2)
        mic_name = "mainmic"



        # Extract the item ID from the response
        scene_items = response2.scene_items  # This contains all items in the scen
        item_id = response.scene_item_id  # Access the scene_item_id attribute
        inside_group_id = group.scene_item_id

        print(f"Scene items in '{scene_items}':")

        if item_id is None:
            print(f"Item '{source_name}' not found in the scene '{scene_name}'.")
            return

        # Print the item ID
        print(f"Item ID for '{source_name}' in scene '{scene_name}': {item_id}")

        client.set_scene_item_enabled(source_name, inside_group_id, enabled=True)
        # Enable the item in the scene
        # client.set_scene_item_enabled(scene_name, item_id, enabled=True)
        print(f"Item '{source_name}' in scene '{scene_name}' has been enabled.")

        client.set_input_mute(mic_name, muted=True)
        print(f"Microphone '{mic_name}' has been muted.")


if __name__ == "__main__":
    get_and_enable_item()
