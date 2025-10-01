    
import os
import json
import requests
from pypdf import PdfReader
import gradio as gr
from dotenv import load_dotenv
import sqlite3
from rapidfuzz import fuzz

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )




class Me:
    def __init__(self):
        self.name = "Krishna Agarwal"
        self.api_key = GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        reader = PdfReader("me/Linkdin.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()

    def system_prompt(self):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, say you don't know and strictly start the sentence with 'I'm sorry'. Be polite and apologising to the client \
If the user is engaging in discussion, try to steer them towards getting in touch via email."

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def setup_database(self):
        self.conn = sqlite3.connect('chat_cache.db',check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_cache (
            question TEXT PRIMARY KEY,
            answer TEXT
        )
    ''')
        self.conn.commit()


    def chat(self, message, history):
        self.cursor.execute('SELECT answer FROM chat_cache WHERE question = ?', (message,))
        row = self.cursor.fetchone()


        best_match = None
        highest_score = 0
        for cached_question, cached_answer in self.cursor.execute('SELECT question, answer FROM chat_cache'):
            similarity = fuzz.token_sort_ratio(message, cached_question)
            if similarity > highest_score:
                highest_score = similarity
                best_match = (cached_question, cached_answer)
        
        if best_match and highest_score>=90:
            print(f"used from cache: {message}")
            return best_match[1]
            

        url = f"{self.base_url}?key={self.api_key}"

        combined_history = f"System: {self.system_prompt()}\n"

        for msg in history:
            role = msg["role"]
            content = msg["content"]
            combined_history += f"{role.capitalize()}: {content}\n"

        combined_history += f"User: {message}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": combined_history}
                    ]
                }
            ]
        }

        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")

        response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

        if "I'm sorry" in response_text:
            push(message)

        self.cursor.execute('INSERT INTO chat_cache (question, answer) VALUES (?, ?)', (message, response_text))
        self.conn.commit()
        print(f"Cached: {message} -> {response_text}")


        return response_text

if __name__ == "__main__":
    me = Me()
    me.setup_database()
    gr.ChatInterface(me.chat, type="messages").launch()
