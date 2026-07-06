from app.rag.utils import json_hash


class ChecksumService:

    @staticmethod
    def calculate(data: dict):

        return json_hash(data)