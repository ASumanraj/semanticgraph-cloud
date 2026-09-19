from fastapi import FastAPI
from .routes import documents, entities

app = FastAPI(title="SemanticGraph Cloud API")

app.include_router(documents.router)
app.include_router(entities.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
