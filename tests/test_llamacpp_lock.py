"""The llama.cpp model wrapper, without llama.cpp: a fake stands in for the model."""


def test_llamacpp_writes_one_answer_at_a_time():
    """llama.cpp has one context per model: two answers must never be written at the same time."""
    import threading
    import time

    from nutriassist.inference.llamacpp_model import LlamaCppChatModel

    class FakeLlama:
        def __init__(self):
            self.active = self.most_active = 0

        def reset(self):
            pass

        def create_chat_completion(self, **kwargs):
            self.active += 1
            self.most_active = max(self.most_active, self.active)
            time.sleep(0.05)
            self.active -= 1
            return {"choices": [{"message": {"content": " answer "}}]}

    llama = FakeLlama()
    model = LlamaCppChatModel(llama)
    threads = [threading.Thread(target=model.generate_batch, args=([[{"role": "user", "content": "q"}]],))
               for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert llama.most_active == 1
    assert model.generate_batch([[{"role": "user", "content": "q"}]]) == ["answer"]
