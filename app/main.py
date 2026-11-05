from fastapi import FastAPI

app = FastAPI(title = "Plataforma Agêntica")

@app.get("/health")
def health():
    return {"status": "okay"}