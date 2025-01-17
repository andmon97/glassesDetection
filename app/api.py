"""
    Module that provide an api for the project
"""
# pylint: disable=protected-access
# pylint: disable=redefined-builtin
# pylint: disable=import-error
# pylint: disable=no-member
# pylint: disable=wrong-import-order


import os
import sys
from datetime import datetime
from functools import wraps
from http import HTTPStatus

import cv2
import numpy as np
from fastapi import Depends, FastAPI, Request, Response
from keras.models import load_model

from fastapi import FastAPI, Request, Response


dir = os.path.dirname(__file__)
sys.path.insert(1, os.path.join(dir))
from schemas import PredictPayload

sys.path.insert(1, os.path.join(dir, "..", "src", "data"))
from make_dataset import _face_alignment

sys.path.insert(1, os.path.join(dir, "..", "app"))
from monitoring import instrumentator

checkpoint_filepath_glasses = os.path.join(
    dir, "..", "models", "finalModelGlassDetection255"
)
best_model_glasses = load_model(checkpoint_filepath_glasses)

# Define application
app = FastAPI(
    title="Project for glass detection",
    description="This API lets you make a prediction wether a subject wears glass",
    version="0.1",
)

instrumentator.instrument(app).expose(app, include_in_schema=False, should_gzip=True)


def construct_response(f):
    """Construct a JSON response for an endpoint's results."""

    @wraps(f)
    def wrap(request: Request, response: Response, *args, **kwargs):
        results = f(request, response, *args, **kwargs)

        # Construct response

        response.status_code = results["status-code"]
        _response = {
            "message": results["message"],
            "method": request.method,
            "timestamp": datetime.now().isoformat(),
            "url": request.url._url,
        }

        # Add data
        if "data" in results:
            response["data"] = results["data"]

        return _response

    return wrap


@app.get("/", tags=["General"])  # path operation decorator
@construct_response
def _index(request: Request, response: Response):
    """Root endpoint."""

    response = {
        "message": "Welcome to glasses classifier! Please, read the `/docs`!",
        "method": request.method,
        "status-code": HTTPStatus.OK,
    }
    return response


@app.post("/predict", tags=["Prediction"])
@construct_response
def prediction_route(
    request: Request,
    response: Response,
    file: PredictPayload = Depends(),
):

    image = file.maybeImage
    # CATCH PredictPayload exception
    if str(image) == "Image needed!":
        error_from_validation = str(image)
        return {
            "message": error_from_validation,
            "method": request.method,
            "status-code": HTTPStatus.NOT_ACCEPTABLE,
        }

    content = image
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    img = _face_alignment(img)

    img_list = []
    img_list.append(img)
    img_list = np.array(img_list)

    prediction_array = best_model_glasses.predict(img_list)
    prediction = prediction_array[0][0]
    prediction = prediction.round()

    if prediction == 1:
        _response = {
            "message": "Glasses detected!",
            "method": request.method,
            "status-code": HTTPStatus.OK,
        }
    else:
        _response = {
            "message": "Glasses NOT detected!",
            "method": request.method,
            "status-code": HTTPStatus.OK,
        }

    response.headers["prediction"] = str(int(prediction))

    return _response
