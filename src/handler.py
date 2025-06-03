from mangum import Mangum
from .api import app

# Create the Lambda handler using Mangum
handler = Mangum(app)