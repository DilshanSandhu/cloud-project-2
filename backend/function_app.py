import azure.functions as func
import logging
import os
import io
import json
import time

import pandas as pd
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

@app.route(route="analyze_diets", auth_level=func.AuthLevel.ANONYMOUS)
def analyze_diets(req: func.HttpRequest) -> func.HttpResponse:

    start_time = time.time()

    try:
        connection_string = os.getenv("DIET_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("DIET_CONTAINER_NAME")
        blob_name = os.getenv("DIET_BLOB_NAME")

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        data = blob_client.download_blob().readall()

        df = pd.read_csv(io.BytesIO(data))

        # Clean data
        df = df.fillna(0)

        # Average nutrients
        avg_macros = (
            df.groupby("Diet_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]]
            .mean()
            .round(2)
            .reset_index()
        )

        # Top protein recipes
        top_protein = (
            df.sort_values("Protein(g)", ascending=False)
            .groupby("Diet_type")
            .head(5)
        )

        # Most common cuisine
        cuisines = (
            df.groupby("Diet_type")["Cuisine_type"]
            .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "")
            .reset_index()
        )

        # Ratios
        df["Protein_to_Carbs"] = (
            df["Protein(g)"] /
            df["Carbs(g)"].replace(0, 1)
        ).round(2)

        df["Carbs_to_Fat"] = (
            df["Carbs(g)"] /
            df["Fat(g)"].replace(0, 1)
        ).round(2)

        execution_time = round(time.time() - start_time, 2)

        result = {
            "average_macros": avg_macros.to_dict(orient="records"),

            "top_protein_recipes":
                top_protein[
                    ["Diet_type",
                     "Recipe_name",
                     "Protein(g)"]
                ].to_dict(orient="records"),

            "most_common_cuisines":
                cuisines.to_dict(orient="records"),

            "execution_time": execution_time
        }

        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:

        logging.exception(e)

        return func.HttpResponse(
            str(e),
            status_code=500
        )