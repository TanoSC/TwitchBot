import asyncio
import json
import os
import uuid
from gtts import gTTS
from pygame import mixer
from twitchio.ext import commands
import websockets
from better_profanity import profanity
import random
import time
import obsws_python as obs
from collections import deque

# Supported Lanauges for TTS with GTTS
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese'
}


class Bot(commands.Bot):

    def __init__(self, token, client_id, broadcaster_id, pubsub_token):
        super().__init__(
            token=token,
            prefix='!',
            initial_channels=['shiini_']
        )
        self.client_id = client_id
        self.broadcaster_id = broadcaster_id
        self.pubsub_token = pubsub_token

        mixer.init()

        # Initialization of various folders for TTS/IMAGE/SOUNDS
        self.tts_directory = os.path.join(os.path.dirname(__file__), 'tts')
        os.makedirs(self.tts_directory, exist_ok=True)
        self.image_directory = os.path.join(os.path.dirname(__file__), 'image')
        os.makedirs(self.image_directory, exist_ok=True)
        self.rewards_sound_directory = os.path.join(os.path.dirname(__file__), 'rewards_sound')
        os.makedirs(self.rewards_sound_directory, exist_ok=True)

        # Initialization of queues.
        self.audio_queue = asyncio.Queue()
        self.reward_queue = deque()  # Unified reward queue
        self.current_tts_file = None
        self.playing_audio = False
        self.is_processing_queue = False
        self.mic_mute_queue = asyncio.Queue()

        # Profanity filter
        self.pf = profanity

        # OBS Websocket connection
        self.obs_host = 'localhost'
        self.obs_port = 4455
        self.obs_password = ''
        # Hl36nxxMTaPlP0Ab
        # berm6jSAmWgYe6gv
        self.obs_client = None  # Connect is initialized in connect_toobs

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User ID is | {self.user_id}')
        channel = self.get_channel('shiini_')
        # if channel:
        #   await channel.send('Connected and ready!')
        # Send message currently commented out]

        # Initialitize various task
        asyncio.create_task(self.process_audio_queue())
        asyncio.create_task(self.listen_to_pubsub())
        asyncio.create_task(self.send_periodic_messages())
        asyncio.create_task(self.process_reward_queue())

        # Connect to OBS
        asyncio.create_task(self.connect_to_obs())

    async def connect_to_obs(self):
        """OBS Connection method, will retry if connection fails"""
        while True:
            try:
                self.obs_client = obs.ReqClient(
                    host=self.obs_host,
                    port=self.obs_port,
                    password=self.obs_password
                )
                print("Connected to OBS WebSocket.")
                return

            except Exception as e:
                print(f"Failed to connect to OBS WebSocket: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

    @commands.command(name='hello')
    async def hello(self, ctx):
        await ctx.send(f'Hello {ctx.author.name}!')

    async def process_reward_queue(self):
        """Process the reward queue and handles it"""
        while True:
            if not self.reward_queue:
                await asyncio.sleep(1)
                continue

            reward_type, reward_data = self.reward_queue.popleft()

            if reward_type == "clown":
                await self.process_clown_reward(reward_data)
            elif reward_type == "anime":
                await self.process_anime_reward(reward_data)
            else:
                print(f"Unknown reward type: {reward_type}")

            await asyncio.sleep(1)

    async def process_clown_reward(self, item_name):
        """Handle the Clown reward."""

        # List of scenes present in Shiini OBS studio
        scenes = [
            "fullscreen miao",
            "Valorant",
            "tft",
            "full camera",
            "mh rise",
            "forza",
            "MHW"
        ]

        # Check if connected
        if not self.obs_client:
            print("OBS client is not connected. Unable to process clown reward.")
            return

        # Enable the requested item (item_name in this case) in all the OBS scenes listed above
        for scene in scenes:
            try:
                response = self.obs_client.get_scene_item_id(scene, item_name)
                item_id = response.scene_item_id

                if item_id is None:
                    print(f"Item '{item_name}' not found in the scene '{scene}'.")
                    continue

                self.obs_client.set_scene_item_enabled(scene, item_id, enabled=True)
                print(f"Item '{item_name}' in scene '{scene}' has been enabled.")
            except Exception as e:
                print(f"Error enabling image in scene '{scene}': {e}")

        await asyncio.sleep(60)

        # Disable all the item enabled before after 60 secs
        for scene in scenes:
            try:
                response = self.obs_client.get_scene_item_id(scene, item_name)
                item_id = response.scene_item_id

                if item_id is None:
                    print(f"Item '{item_name}' not found in the scene '{scene}'.")
                    continue

                self.obs_client.set_scene_item_enabled(scene, item_id, enabled=False)
                print(f"Item '{item_name}' in scene '{scene}' has been disabled.")
            except Exception as e:
                print(f"Error disabling image in scene '{scene}': {e}")

    async def process_anime_reward(self, item_name):
        """Handle the anime reward."""
        # Work in progress
        print(f"Processing anime reward with item: {item_name}")

    async def send_new_messages(self, ctx):
        """Bot introduction."""
        # Define the messages
        messages = [
            f"Hello {ctx.author.name}! 🎉 I'm the new and improved bot made by @TanoSC0 (shameless plug) with new features 🚀",
            "🌐 TTS language selection by typing -en, -es, -fr, -de, -it, -pt, -ru, -ja, -ko, -zh before your TTS message! (example: -ko Hello)",
            "🎬 Interact with OBS to change the stream scene or mute shiini when he's yapping too much! ",
            "🎵 New anime sounds and more secrets! AYAYA"
        ]

        # Delays messages to avoid rate limit (maybe, idk if twitch does rate limit)
        for message in messages:
            await ctx.send(message)
            await asyncio.sleep(2)

    @commands.command(name='new')
    async def hello(self, ctx):
        await self.send_new_messages(ctx)

    async def process_audio_queue(self):
        """Process commands from the audio queue"""
        while True:
            command, file_path = await self.audio_queue.get()
            if command == 'song':
                await self.play_audio(file_path)
            elif command == 'tts':
                await self.play_audio(file_path)

            self.audio_queue.task_done()

    async def play_audio(self, file_path):
        """Play an audio file and ensure no overlap by queueing"""
        if self.playing_audio:
            await self.audio_queue.put(('skip', file_path))
            return

        self.playing_audio = True

        try:
            mixer.music.load(file_path)
            mixer.music.play()
            while mixer.music.get_busy():
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error playing audio: {e}")
        finally:
            self.playing_audio = False

    async def listen_to_pubsub(self):
        """Connect to Twitch PubSub to listen for channel points redemptions."""
        pubsub_url = "wss://pubsub-edge.twitch.tv"

        while True:
            try:
                async with websockets.connect(pubsub_url) as ws:
                    # Send listen message to subscribe to channel points events
                    listen_message = {
                        "type": "LISTEN",
                        "nonce": str(uuid.uuid4()),
                        "data": {
                            "topics": [f"channel-points-channel-v1.{self.broadcaster_id}"],
                            "auth_token": self.pubsub_token
                        }
                    }
                    await ws.send(json.dumps(listen_message))
                    print("Listening for Channel Point Redemptions...")

                    # Loop to continously listen to pubsub connection
                    while True:
                        try:
                            response = await ws.recv()  # Receive message
                            response_data = json.loads(response)

                            if response_data["type"] == "MESSAGE":
                                message_data = json.loads(response_data["data"]["message"])
                                redemption = message_data['data']['redemption']
                                reward_title = redemption['reward']['title']
                                user_input = redemption.get('user_input')
                                print(f"Channel Point Reward Redeemed: {reward_title}")

                                # Check which reward has been redeemed (TTS or others)
                                if reward_title == "«TTS»" and user_input:
                                    await self.handle_tts_redemption(user_input)  # Handle TTS specifically
                                else:
                                    # Handle other sound-related rewards
                                    await self.handle_reward_redemption(reward_title)

                        except websockets.ConnectionClosedError:
                            print("Connection lost... reconnecting.")
                            break
                        except asyncio.IncompleteReadError:
                            print("Incomplete read error... reconnecting.")
                            break
                        except Exception as e:
                            print(f"Error in message handling: {e}")

            except (websockets.ConnectionClosedError, asyncio.IncompleteReadError) as e:
                print(f"WebSocket connection error: {e}. Reconnecting in 5 seconds.")
            except Exception as e:
                print(f"Unexpected error: {e}. Reconnecting in 5 seconds.")

            # Wait before trying to reconnect
            await asyncio.sleep(5)

    async def handle_reward_redemption(self, reward_title):
        """Handle specific channel point rewards and play corresponding audio"""

        # One reward name will be associated with all the audios it can play, if more than one it will choose
        # randomly
        reward_to_audio = {
            "[Thunder]": ["scary/thunder_good.mp3", "scary/thunder_scuffed.mp3"],
            "[Door Sound]": ["scary/door_right.mp3", "scary/door_left.mp3"],
            "[Steps]": ["scary/steps_left.mp3", "scary/steps_right.mp3"],
            "[Hydrohomie]": ["hydro/drink.mp3"],
            "[Action is Coming]": ["scary/action_is_coming_reverb.mp3"],
            "[Running steps]": ["scary/running_left.mp3"],
            "«Gnome»": ["gnome/gnome.mp3"],
            "Random Anime Sound": [
                "anime_random/animu-door.mp3", "anime_random/animu-punch.mp3", "anime_random/animu-slip.mp3",
                "anime_random/good-job.mp3", "anime_random/grats.mp3", "anime_random/hentai-kanna.mp3",
                "anime_random/long-thingy.mp3", "anime_random/nico-nico-ni.mp3", "anime_random/nom.mp3",
                "anime_random/oh-my-gawd.mp3", "anime_random/oh-my-gawd-jojo.mp3",
                "anime_random/random-obama-idk-lul.mp3",
                "anime_random/single-ora.mp3", "anime_random/souka.mp3", "anime_random/sugoi-sugoi.mp3",
                "anime_random/tutturuuuu.mp3", "anime_random/suki-suki.mp3", "anime_random/summer-time.mp3",
                "anime_random/uwu.mp3", "anime_random/giorno.mp3", "anime_random/gofast.mp3", "anime_random/ruski.mp3",
                "anime_random/scatman.mp3", "anime_random/pogchamp.mp3", "anime_random/tole-tole.mp3",
                "anime_random/coso.mp3", "anime_random/caramel.mp3", "anime_random/ara-ara.mp3",
                "anime_random/uwu2.mp3", "anime_random/ganbate.mp3", "anime_random/tbc.mp3"],
            "«Random Valorant Sound»": ["announcer/ATTACKER_WIN.mp3", "announcer/ONE_LEFT.mp3",
                                        "announcer/SPIKE_PLANTED.mp3",
                                        "announcer/TEN_SECONDS.mp3"],
            "«Random Ulti»": ["ultimate/BREACH_ULTIMATE.mp3", "ultimate/BRIM_ULTIMATE.mp3",
                              "ultimate/CYPHER_ULTIMATE.mp3",
                              "ultimate/JETT_ULTIMATE.mp3", "ultimate/OMEN_ULTIMATE.mp3",
                              "ultimate/PHOENIX_ULTIMATE.mp3", "ultimate/RAZE_ULTIMATE.mp3",
                              "ultimate/REYNA_ULTIMATE.mp3", "ultimate/SAGE_ULTIMATE.mp3",
                              "ultimate/SOVA_ULTIMATE.mp3", "ultimate/VIPER_ULTIMATE.mp3"],
            "[Meme Scream]": ["scary/gachi_scream.mp3"],
            "[Random Gachi]": [f"random/{i}.mp3" for i in range(1, 19)],  # TO-DO remove rewrite this line, this
            # doesn't work.
            "[Gachi big F]": ["gachi_big_f/FUCK_YOU.mp3"],
            "[That's amazing]": ["thats_amazing/thatsamazing.mp3"],
            "[Hey Vsauce]": ["vsauce/Vsauce.mp3"],
            "Bonk": ["anime_bonk/bonk1.mp3", "anime_bonk/bonk2.mp3", "anime_bonk/bonk3.mp3"],
            "Random JOJO Fight": ["jojo_fight/arrivederci.arrivederci.mp3", "jojo_fight/muda-muda-muda.mp3",
                                  "jojo_fight/ora-ora-ora.mp3", "jojo_fight/joelynora.mp3", "jojo_fight/giornomuda.mp3"]
        }

        if reward_title == "🤡Clown🤡":  # if clown will append to the queue the request
            # Handle 🤡Clown🤡 reward
            self.reward_queue.append(("clown", "Clown"))  # Synchronous append
            print("Queued 🤡Clown🤡 reward.")

        if reward_title in reward_to_audio:
            if reward_title == "«Gnome»":  # Gnome is handled a bit different because it has a 60% chance of repeating
                gnome_audio = reward_to_audio[reward_title][0]
                full_path = os.path.join(self.rewards_sound_directory, gnome_audio)
                print(f"Queuing gnome audio file: {full_path}")
                await self.audio_queue.put(('song', full_path))

                # Roll for additional gnomes (60% chance for each additional one)
                while random.random() < 0.6:  # 60% chance
                    print(f"60% chance succeeded, queuing another gnome: {full_path}")
                    await self.audio_queue.put(('song', full_path))

            else:
                # For other rewards, pick a random audio from the list
                audio_file = random.choice(reward_to_audio[reward_title])
                full_path = os.path.join(self.rewards_sound_directory, audio_file)
                print(f"Queuing audio file: {full_path}")
                await self.audio_queue.put(('song', full_path))

            # Handle the "No Yap" reward to mute the microphone
        if reward_title == "No Yap":
            # Add the mute request to the queue
            await self.mic_mute_queue.put('mute')
            print("Queued microphone mute request for 'No Yap'.")
            asyncio.create_task(self.process_mic_mute_queue())

    async def process_mic_mute_queue(self):
        """Process the mute queue reward to mute the mic for 10 seconds"""
        while not self.mic_mute_queue.empty():
            await self.mic_mute_queue.get()

            mic_name = "Main mic"

            # Check if OBS is connected
            if not self.obs_client:
                print("OBS client is not connected. Unable to mute the mic.")
                return

            try:
                # Mute the microphone
                self.obs_client.set_input_mute(mic_name, muted=True)
                print(f"Microphone '{mic_name}' has been muted.")
                await self.get_channel('shiini_').send(f"Stop yapping @shiini_ is now muted.")

                # Wait for 10 seconds
                await asyncio.sleep(10)

                # Unmute the microphone
                self.obs_client.set_input_mute(mic_name, muted=False)
                print(f"Microphone '{mic_name}' has been unmuted.")

            except Exception as e:
                print(f"Error muting/unmuting microphone: {e}")
                await self.get_channel('shiini_').send(f"Error: could not redeem 'No Yap' reward.")

            self.mic_mute_queue.task_done()

    async def handle_tts_redemption(self, user_input):
        """Handle TTS redemptions by parsing input for language and text, adding to the audio queue"""
        if not user_input:
            print("No text provided for TTS.")
            return

        # Default language is english
        language = 'en'

        # Check if the input starts with a language flag (example: -en, -it, etc.)
        words = user_input.split()
        if words[0].startswith('-') and len(words[0]) > 1:
            lang_code = words[0][1:]
            if lang_code in SUPPORTED_LANGUAGES:
                language = lang_code
                text = ' '.join(words[1:])
            else:
                print(f"Unsupported language code: {lang_code}. Defaulting to English.")
                text = ' '.join(words)  # If language code is unsupported, use the whole input as text
        else:
            text = ' '.join(words)  # If no language code is provided, use the whole input as text

        # Check for profanity
        if self.pf.contains_profanity(text):
            await self.get_channel('shiini_').send(f'This is a Christian channel, no swearing.')
            return  # It will skip if teh TTS contains blacklisted words.

        # Generate the TTS mp3 file with an unique ID
        unique_filename = f"{uuid.uuid4()}.mp3"
        temp_file_path = os.path.join(self.tts_directory, unique_filename)
        try:
            tts = gTTS(text=text, lang=language)
            tts.save(temp_file_path)
            print(f"TTS file created: {temp_file_path}")
        except Exception as e:
            print(f"Error generating TTS: {e}")
            return

        # Add the TTS file to the audio queue
        await self.audio_queue.put(('tts', temp_file_path))
        print(f"TTS queued for playback: {text} in {language}")

    async def send_periodic_messages(self):
        """Send periodic messages every 60 and 90 minutes"""
        while True:
            try:
                # water reminder every 60 minutes
                await asyncio.sleep(60 * 60)
                await self.get_channel('shiini_').send('Remember to drink water and stay hydrated!')

                # HeyGuys message every 90 minutes
                await asyncio.sleep(90 * 60)
                await self.get_channel('shiini_').send('HeyGuys!')
            except Exception as e:
                print(f"Error in periodic messages: {e}")


# Initialization token etc...
if __name__ == '__main__':
    token = ''
    client_id = ''
    broadcaster_id = ''
    pubsub_token = ''

    bot = Bot(token, client_id, broadcaster_id, pubsub_token)
    bot.run()
