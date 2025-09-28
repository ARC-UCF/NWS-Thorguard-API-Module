from . import reference_locations
import config

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.io.shapereader import natural_earth, Reader
from cartopy.feature import ShapelyFeature
from shapely.geometry import Point, Polygon, MultiPolygon
import geopandas as gpd
import math
import matplotlib.pyplot as plt
from io import BytesIO

ucf = Point(-81.2001, 28.6024) # UCF coords for shapely polygon checking
ucf_point = gpd.GeoSeries([Point(ucf)], crs="EPSG:4326") # Converting UCF to GeoSeries now so we aren't doing this over and over again for just one point.
ucf_point = ucf_point.to_crs(epsg=6439) # Convert to local CRS, this one being Florida East in meters.

roads_shp = "natural_earth/roads/ne_10m_roads_north_america.shp" # Natural Earth road shapefile path.
lakes_base_shp = "natural_earth/lakes_base/ne_10m_lakes.shp"
rivers_base_shp = "natural_earth/rivers_base/ne_10m_rivers_lake_centerlines.shp"
lakes_supp_shp = "natural_earth/lakes_supp_ne/ne_10m_lakes_north_america.shp"
rivers_supp_shp = "natural_earth/rivers_supp_ne/ne_10m_rivers_north_america.shp"
urban_shp = "natural_earth/urban/ne_10m_urban_areas.shp"

def ucf_in_or_near_polygon(geodat: list) -> tuple[bool, str]: # Specific to figuring out if UCF is included or near the alert polygon, only for WEAS handling.
    if not geodat:
        return False, ""
    
    poly = Polygon(geodat)

    if ucf.within(poly):
        return True, "within"
    else: # Handle logic to find out if this alert polygon is near UCF.
        gdf_alert = gpd.GeoSeries([poly], crs="EPSG:4326")

        gdf_alert = gdf_alert.to_crs(epsg=6439)  # NAD83 / Florida East (meters)

        # Buffer UCF point by X miles (1 mile ≈ 1609.34 m)
        pBuffer = ucf_point.buffer(config.bufferMiles * 1609.34)

        # Check if alert polygon intersects the buffered area
        intersects = gdf_alert.intersects(pBuffer.iloc[0])[0]

        if intersects:
            return True, "around"
    return False, ""
    
def filter_points_in_bounds(points: list, bounds: float) -> list:
    """
    points: list of tuples (name, lat, lon)
    bounds: min_lon, max_lon, min_lat, max_lat
    returns: filtered list of points inside bounds
    """
    min_lon, max_lon, min_lat, max_lat = bounds
    filtered = []
    for name, lat, lon in points:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            filtered.append((name, lat, lon))
    return filtered

def get_bounds_from_multipoylgon(multipoly, buffer_miles=0):
    if multipoly is None:
        return None
    
    # Flatten all exterior coordinates of all polygons
    coords = [pt for poly in multipoly.geoms for pt in poly.exterior.coords]

    lons, lats = zip(*coords)
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    if buffer_miles > 0:
        lat_buffer = buffer_miles * 0.0145
        avg_lat = sum(lats) / len(lats)
        lon_buffer = buffer_miles * 0.0145 / max(0.0001, abs(math.cos(math.radians(avg_lat))))
        min_lon -= lon_buffer
        max_lon += lon_buffer
        min_lat -= lat_buffer
        max_lat += lat_buffer

    return min_lon, max_lon, min_lat, max_lat

def safe_geometries(reader):
    return [g for g in reader.geometries() if g is not None]

def generate_alert_image(coords: list, base: str, alertCode: str, polyColor: str, trackId: str):
    '''
    All CSS colors are valid for facecolors and edgecolors.
    
    Alternatively, you can define hexcodes for colors for different layers.
    '''
    
    if not coords: # If we have no coords, return so we don't error.
        return None
    
    multipoly = None # Define multipoly.
    
    if base == "Polygon": # If a single polygon.
        print(coords[0])
        multipoly = MultiPolygon([Polygon(coords[0])]) # Still make it a multipolygon for easier use.
    elif base == "Area": # If area, and therefore, potentially multiple poylgons.
        polygons = []
        for mp in coords:
            for ply in mp:
                polygons.append(Polygon(ply[0]))
        multipoly = MultiPolygon(polygons)
    else:
        return None # If base is neither Polygon or Area, exit and return None.
    
    if polyColor is None:
        polyColor = '#6e6e6e'
    
    minx, miny, maxx, maxy = multipoly.bounds # Define bounds.
    
    fig, ax = plt.subplots(
        figsize=(14, 10),
        subplot_kw={'projection': ccrs.PlateCarree()}
    )
    
    # Below is every layer included for alert image generation. Change colors how you like, but make sure they work.
    # And work as in they are still readable and don't hurt the eyes.
    
    ax.add_feature(cfeature.LAND.with_scale('10m'), facecolor='lightgray', zorder=1)
    ax.add_feature(cfeature.OCEAN.with_scale('10m'), facecolor='lightblue', zorder=1)
    ax.add_feature(cfeature.LAKES.with_scale('10m'), facecolor='lightblue', zorder=2)
    ax.add_feature(cfeature.RIVERS.with_scale('10m'), edgecolor='blue', zorder=2)
    ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor='black', zorder=3)
    ax.add_feature(cfeature.STATES.with_scale('10m'), edgecolor='black', zorder=3)
    
    counties_shp = natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
    counties_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(counties_shp)),
        crs=ccrs.PlateCarree(),
        facecolor='none',
        edgecolor='red',
        linewidth=1,
        zorder=3,
    )
    if counties_feature is not None:
        ax.add_feature(counties_feature)

    roads_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(roads_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none',
        zorder=4,
    )
    if roads_feature is not None:
        ax.add_feature(roads_feature)
        
    lakes_base_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(lakes_base_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='blue',  # whatever color you like
        facecolor='blue',
        zorder=3,
    )
    if lakes_base_feature is not None:
        ax.add_feature(lakes_base_feature)
        
    rivers_base_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(lakes_base_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='blue',  # whatever color you like
        facecolor='blue',
        zorder=3,
    )
    if rivers_base_feature is not None:
        ax.add_feature(rivers_base_feature)
        
    lakes_supp_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(lakes_supp_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='blue',  # whatever color you like
        facecolor='blue',
        zorder=3,
    )
    if lakes_supp_feature is not None:
        ax.add_feature(lakes_supp_feature)
        
    rivers_supp_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(rivers_supp_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='blue',  # whatever color you like
        facecolor='blue',
        zorder=3,
    )
    if rivers_supp_feature is not None:
        ax.add_feature(rivers_supp_feature)
    
    urban_feature = ShapelyFeature(
        geometries=safe_geometries(Reader(urban_shp)),
        crs=ccrs.PlateCarree(),
        edgecolor='darkslategray',  # whatever color you like
        facecolor='darkslategray',
        zorder=4,
    )
    if urban_feature is not None:
        ax.add_feature(urban_feature)
        
    for poly in multipoly.geoms:
        if poly:
            x, y = poly.exterior.xy
            ax.plot(x, y, color=polyColor, linewidth=2, transform=ccrs.PlateCarree(), zorder=5)
            ax.fill(x, y, color=polyColor, alpha=0.2, transform=ccrs.PlateCarree(), zorder=5)
        else:
            print("poly is invalid")
        
    lon_pad = 0.5  # wider east-west
    lat_pad = 0.25  # shorter north-south
    ax.set_extent([minx - lon_pad, maxx + lon_pad, miny - lat_pad, maxy + lat_pad], crs=ccrs.PlateCarree())
    
    bounds = get_bounds_from_multipoylgon(multipoly, 10)
    
    filtered_points = filter_points_in_bounds(reference_locations.city_points, bounds)
    
    for name, lat, lon in filtered_points:
        ax.scatter(lon, lat, color='blue', s=30, transform=ccrs.PlateCarree(), zorder=6)
        ax.text(lon, lat + 0.01, name, fontsize=8, transform=ccrs.PlateCarree(), zorder=6)
        
    buf = BytesIO()
    plt.tight_layout()
    plt.title(
        label=f"Alert Area - {alertCode} - #{trackId}", 
        loc='left',
        fontsize=24,
    )
    print("Multipolygon info:")
    for poly in multipoly.geoms:
        print(f"Polygon valid: {poly.is_valid}, {len(poly.exterior.coords)} coords")
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def test_image_generation(): # Function is unused. Keep for testing image generation with new layers to ensure they work before push to production.
    '''
    All CSS colors are valid for facecolors and edgecolors.
    
    Altneratively, you can define hexcodes for colors for different layers.
    '''
    
    fig, ax = plt.subplots(
        figsize=(14, 10),
        subplot_kw={'projection': ccrs.PlateCarree()}
    )
    
    ax.add_feature(cfeature.LAND.with_scale('10m'), facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN.with_scale('10m'), facecolor='lightblue')
    ax.add_feature(cfeature.LAKES.with_scale('10m'), facecolor='lightblue')
    ax.add_feature(cfeature.RIVERS.with_scale('10m'), edgecolor='blue')
    ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor='black')
    ax.add_feature(cfeature.STATES.with_scale('10m'), edgecolor='black')
    
    counties_shp = natural_earth(resolution='10m', category='cultural', name='admin_2_counties')
    counties_feature = ShapelyFeature(
        geometries=Reader(counties_shp).geometries(),
        crs=ccrs.PlateCarree(),
        facecolor='none',
        edgecolor='red',
        linewidth=1
    )
    if counties_feature is not None:
        ax.add_feature(counties_feature)

    roads_feature = ShapelyFeature(
        Reader(roads_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none'
    )
    if roads_feature is not None:
        ax.add_feature(roads_feature)
        
    lakes_base_feature = ShapelyFeature(
        Reader(lakes_base_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none'
    )
    if lakes_base_feature is not None:
        ax.add_feature(lakes_base_feature)
        
    rivers_base_feature = ShapelyFeature(
        Reader(rivers_base_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none'
    )
    if rivers_base_feature is not None:
        ax.add_feature(rivers_base_feature)
        
    lakes_supp_feature = ShapelyFeature(
        Reader(lakes_supp_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none'
    )
    if lakes_supp_feature is not None:
        ax.add_feature(lakes_supp_feature)
        
    rivers_supp_feature = ShapelyFeature(
        Reader(rivers_supp_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='grey',  # whatever color you like
        facecolor='none'
    )
    if rivers_supp_feature is not None:
        ax.add_feature(rivers_supp_feature)
        
    urban_feature = ShapelyFeature(
        Reader(urban_shp).geometries(),
        crs=ccrs.PlateCarree(),
        edgecolor='darkslategray',  # whatever color you like
        facecolor='none'
    )
    if urban_feature is not None:
        ax.add_feature(urban_feature)
        
    plt.tight_layout()
    plt.close(fig)
    print("completed image.")
    
