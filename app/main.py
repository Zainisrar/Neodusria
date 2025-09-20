from fastapi import FastAPI
from app.routes import users, news_alerts, dashboard, global_markets, technology_innovation, regulation, competitive

app = FastAPI(title="Neodustria API")

# Register routers
app.include_router(users.router)
app.include_router(news_alerts.router)
app.include_router(dashboard.router)
app.include_router(global_markets.router)
app.include_router(technology_innovation.router)
app.include_router(regulation.router)
app.include_router(competitive.router)

@app.get("/")
def root():
    return {"message": "Neodustria API is running!"}
