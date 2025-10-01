from vercel_asgi import VercelASGI
from main import app as fastapi_app

handler = VercelASGI(fastapi_app)
