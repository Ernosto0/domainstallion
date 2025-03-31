import uvicorn
import os

# Get environment
env = os.getenv("ENVIRONMENT", "development")
is_production = env == "production"

if __name__ == "__main__":
    # Production settings: multiple workers, no reload, production log level
    if is_production:
        # Number of workers based on CPU cores (2 * num_cores + 1) is a common formula
        # For simplicity, setting to 4 workers, but adjust based on your server resources
        uvicorn.run(
            "backend.main:app", 
            host="0.0.0.0", 
            port=int(os.getenv("PORT", "8000")),
            reload=False,
            workers=4,
            access_log=True,
            log_level="info"
        )
    else:
        # Development settings: reload enabled, single worker, debug log level
        uvicorn.run(
            "backend.main:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="debug"
        )
