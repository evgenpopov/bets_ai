import random


class BaseAIModel:
    name = "Base"

    def predict(self, fight_info):
        raise NotImplementedError


class ChatGPTModel(BaseAIModel):
    name = "ChatGPT"

    def predict(self, fight_info):
        return random.choice([fight_info["fighter1"], fight_info["fighter2"]])


class DeepSeekModel(BaseAIModel):
    name = "DeepSeek"

    def predict(self, fight_info):
        return random.choice([fight_info["fighter1"], fight_info["fighter2"]])


class GeminiModel(BaseAIModel):
    name = "Gemini"

    def predict(self, fight_info):
        return random.choice([fight_info["fighter1"], fight_info["fighter2"]])