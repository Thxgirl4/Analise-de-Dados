import os
import json
import time
import numpy as np
import geopandas as gpd
import rasterio
import rasterio.mask
import openeo
from shapely.geometry import box
from datetime import datetime, timedelta
from itertools import product


class NDVIProcessor:
    def __init__(self, connection, output_dir, resolution=0.0009, quadrant_size=1):
        self.connection = connection
        self.output_dir = output_dir
        self.resolution = resolution
        self.quadrant_size = quadrant_size
        os.makedirs(output_dir, exist_ok=True)

    def generate_last_15_days(self):
        """Gera uma lista de datas para os últimos 15 dias."""
        end_date = datetime.today()
        start_date = end_date - timedelta(days=14)
        return [(start_date + timedelta(days=x)).strftime("%Y-%m-%d") for x in range(15)]

    def load_quadrants(self, shapefile_path):
        """Carrega o shapefile e cria quadrantes."""
        gdf = gpd.read_file(shapefile_path)
        minx, miny, maxx, maxy = gdf.total_bounds

        x_coords = np.arange(minx, maxx, self.quadrant_size)
        y_coords = np.arange(miny, maxy, self.quadrant_size)

        return [
            box(x, y, min(x + self.quadrant_size, maxx), min(y + self.quadrant_size, maxy))
            for x, y in product(x_coords, y_coords)
        ]

    def process_quadrant(self, quadrant, quadrant_index, date_list):
        """Processa um quadrante para encontrar a melhor imagem NDVI."""
        quadrant_start_time = time.time()
        quadrant_output_dir = os.path.join(self.output_dir, f"quadrant_{quadrant_index}")
        os.makedirs(quadrant_output_dir, exist_ok=True)

        # Verifica se já existe um arquivo NDVI processado
        if any(f.endswith(".tif") for f in os.listdir(quadrant_output_dir)):
            print(f"Quadrante {quadrant_index} já processado. Pulando para o próximo.")
            return

        geom = json.loads(gpd.GeoSeries([quadrant]).to_json())["features"][0]["geometry"]
        bbox_extent = {'west': quadrant.bounds[0], 'south': quadrant.bounds[1],
                       'east': quadrant.bounds[2], 'north': quadrant.bounds[3]}

        best_image = None
        least_nodata_ratio = 1.0

        for date in date_list:
            try:
                print(f"Processando quadrante {quadrant_index}, data: {date}")
                ndvi_image, nodata_ratio = self.get_ndvi_image(bbox_extent, date)

                print(f"Data {date}: {nodata_ratio * 100:.2f}% pixels vazios.")

                if best_image is None or nodata_ratio < least_nodata_ratio:
                    best_image = ndvi_image
                    least_nodata_ratio = nodata_ratio

                if nodata_ratio == 0:
                    print(f"Imagem completa encontrada para quadrante {quadrant_index} na data {date}.")
                    break

            except openeo.rest.JobFailedException:
                print(f"Sem dados válidos para {date}, quadrante {quadrant_index}.")
                continue
            except openeo.rest.OpenEoApiError as e:
                print(f"Erro no servidor: {str(e)}, esperando para tentar novamente.")
                time.sleep(10)
                continue

        if best_image:
            self.save_ndvi_image(best_image, quadrant_output_dir, quadrant_index)

        print(f"Tempo do quadrante {quadrant_index}: {time.time() - quadrant_start_time:.2f} segundos")

    def get_ndvi_image(self, bbox_extent, date):
        """Obtém e processa a imagem NDVI de um dado quadrante e data."""
        datacube = self.connection.load_collection(
            "SENTINEL2_L2A",
            spatial_extent=bbox_extent,
            temporal_extent=[date, date],
            bands=["B04", "B08"],
            max_cloud_cover=99,
        )

        datacube_ndvi = datacube.ndvi(nir="B08", red="B04").resample_spatial(
            resolution=self.resolution,
            projection="EPSG:4326",
            method="near"
        )

        temp_tiff = "temp_ndvi.tif"
        datacube_ndvi.download(temp_tiff)

        with rasterio.open(temp_tiff) as src:
            out_image, out_transform = rasterio.mask.mask(
                src, [bbox_extent], crop=True, filled=True, nodata=np.nan
            )
            out_meta = src.meta.copy()

        nodata_pixels = np.isnan(out_image).sum()
        total_pixels = out_image.size
        nodata_ratio = nodata_pixels / total_pixels

        os.remove(temp_tiff)

        return {"image": out_image, "transform": out_transform, "meta": out_meta, "date": date}, nodata_ratio

    def save_ndvi_image(self, best_image, output_dir, quadrant_index):
        """Salva a melhor imagem NDVI encontrada."""
        final_tiff = f"{output_dir}/ndvi_quadrant_{quadrant_index}_{best_image['date']}.tif"
        best_image['meta'].update({
            "driver": "GTiff",
            "height": best_image['image'].shape[1],
            "width": best_image['image'].shape[2],
            "transform": best_image['transform'],
            "nodata": np.nan
        })

        with rasterio.open(final_tiff, "w", **best_image['meta']) as dest:
            dest.write(best_image['image'])

        print(f"Melhor imagem salva para quadrante {quadrant_index} na data {best_image['date']}.")


# ----------- EXECUÇÃO -----------
if __name__ == "__main__":
    # Conectar ao OpenEO
    connection = openeo.connect("openeo.dataspace.copernicus.eu")
    connection.authenticate_oidc(store_refresh_token=True)

    processor = NDVIProcessor(
        connection=connection,
        output_dir="",
        resolution=0.0009,
        quadrant_size=1
    )

    shapefile_path = ""
    quadrants = processor.load_quadrants(shapefile_path)
    date_list = processor.generate_last_15_days()

    for i, quadrant in enumerate(quadrants):
        processor.process_quadrant(quadrant, i, date_list)
