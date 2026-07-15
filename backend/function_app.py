import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


@app.route(
    route="analyze_diets",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def analyze_diets(req: func.HttpRequest) -> func.HttpResponse:
    """Read the diets dataset from Azure Blob Storage and return analysis."""

    start_time = time.perf_counter()

    try:
        # Read Azure application settings
        connection_string = os.getenv("DIET_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("DIET_CONTAINER_NAME", "diet-data")
        blob_name = os.getenv("DIET_BLOB_NAME", "All_Diets.csv")

        if not connection_string:
            raise ValueError(
                "DIET_STORAGE_CONNECTION_STRING is not configured."
            )

        # Connect to Azure Blob Storage
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        # Download and load the CSV file
        blob_data = blob_client.download_blob().readall()
        df = pd.read_csv(io.BytesIO(blob_data))

        required_columns = [
            "Diet_type",
            "Recipe_name",
            "Cuisine_type",
            "Protein(g)",
            "Carbs(g)",
            "Fat(g)"
        ]

        missing_columns = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Dataset is missing required columns: {missing_columns}"
            )

        # Remove rows without a diet type
        df = df.dropna(subset=["Diet_type"])

        # Clean text columns
        df["Diet_type"] = (
            df["Diet_type"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        df["Recipe_name"] = (
            df["Recipe_name"]
            .fillna("Unknown Recipe")
            .astype(str)
            .str.strip()
        )

        df["Cuisine_type"] = (
            df["Cuisine_type"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .str.title()
        )

        # Convert nutrition columns to numeric values
        nutrient_columns = ["Protein(g)", "Carbs(g)", "Fat(g)"]

        for column in nutrient_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
            df[column] = df[column].fillna(df[column].mean()).fillna(0)

        # Calculate average nutrients by diet type
        average_macros = (
            df.groupby("Diet_type")[nutrient_columns]
            .mean()
            .round(2)
            .reset_index()
        )

        # Find the top five protein-rich recipes for each diet type
        top_protein_recipes = (
            df.sort_values("Protein(g)", ascending=False)
            .groupby("Diet_type", group_keys=False)
            .head(5)
            [
                [
                    "Diet_type",
                    "Recipe_name",
                    "Cuisine_type",
                    "Protein(g)"
                ]
            ]
            .round({"Protein(g)": 2})
        )

        # Find the most common cuisine for each diet
        most_common_cuisines = (
            df.groupby("Diet_type")["Cuisine_type"]
            .agg(
                lambda values:
                values.mode().iloc[0]
                if not values.mode().empty
                else "Unknown"
            )
            .reset_index(name="Most_common_cuisine")
        )

        # Calculate nutrient ratios safely
        nonzero_carbs = df["Carbs(g)"].replace(0, pd.NA)
        nonzero_fat = df["Fat(g)"].replace(0, pd.NA)

        df["Protein_to_Carbs_ratio"] = (
            df["Protein(g)"] / nonzero_carbs
        ).fillna(0).round(2)

        df["Carbs_to_Fat_ratio"] = (
            df["Carbs(g)"] / nonzero_fat
        ).fillna(0).round(2)

        average_ratios = (
            df.groupby("Diet_type")
            [
                [
                    "Protein_to_Carbs_ratio",
                    "Carbs_to_Fat_ratio"
                ]
            ]
            .mean()
            .round(2)
            .reset_index()
        )

        # Find diet type with the highest average protein
        highest_protein_row = average_macros.loc[
            average_macros["Protein(g)"].idxmax()
        ]

        execution_time = round(
            time.perf_counter() - start_time,
            3
        )

        result = {
            "status": "success",
            "dataset": {
                "container": container_name,
                "blob": blob_name,
                "total_recipes": int(len(df)),
                "total_diet_types": int(df["Diet_type"].nunique())
            },
            "average_macros": average_macros.to_dict(
                orient="records"
            ),
            "top_protein_recipes": top_protein_recipes.to_dict(
                orient="records"
            ),
            "most_common_cuisines": most_common_cuisines.to_dict(
                orient="records"
            ),
            "average_ratios": average_ratios.to_dict(
                orient="records"
            ),
            "highest_protein_diet": {
                "Diet_type": highest_protein_row["Diet_type"],
                "Average_protein_g": round(
                    float(highest_protein_row["Protein(g)"]),
                    2
                )
            },
            "execution_time_seconds": execution_time
        }

        return func.HttpResponse(
            body=json.dumps(result),
            status_code=200,
            mimetype="application/json",
            charset="utf-8"
        )

    except Exception as error:
        logging.exception("Diet analysis function failed.")

        error_response = {
            "status": "error",
            "message": str(error)
        }

        return func.HttpResponse(
            body=json.dumps(error_response),
            status_code=500,
            mimetype="application/json",
            charset="utf-8"
        )