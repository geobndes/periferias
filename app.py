import streamlit as st
import geopandas as gpd
import folium
from geopy import Point as GeopyPoint
from geopy.geocoders import ArcGIS
from shapely.geometry import Point
from streamlit_folium import st_folium
import numpy as np
import pandas as pd

# Carrega bases de dados relevantes

# 1. Favelas e Comunidades Urbanas
fcus = gpd.read_file("Favelas e Comunidades Urbanas/poligonos_FCUs_shp/qg_2022_670_fcu_agreg.shp")
fcus['fcus_geometry'] = fcus.geometry

# 2. Tipologia Intraurbana
tipologia = gpd.read_file('Tipologia Intraurbana/TipologiaIntraUrbana.shp')
tipologia['tipologia_geometry'] = tipologia.geometry

# Funções auxiliares

def dms_to_point(dms):
    geo_point = GeopyPoint(dms)
    lat_dd, lon_dd = geo_point.latitude, geo_point.longitude
    point = Point(lon_dd, lat_dd)
    return point

def cria_df_com_nome_coord(nome_do_ponto, coordenadas):
    dados_bndes_periferias = {
        'nome': [nome_do_ponto],
        'coord_dms': [coordenadas]
    }
    gdf_bndes_periferias = gpd.GeoDataFrame(dados_bndes_periferias)
    gdf_bndes_periferias['points_geometry'] = gdf_bndes_periferias['coord_dms'].map(dms_to_point)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def cria_df_com_nome_latlon(nome_do_ponto, latitude, longitude):
    dados_bndes_periferias = {
        'nome': [nome_do_ponto],
        'points_geometry': [Point(longitude, latitude)]
    }
    gdf_bndes_periferias = gpd.GeoDataFrame(dados_bndes_periferias)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def cria_df_com_csv_latlon(csv_file):
    gdf_bndes_periferias = pd.read_csv(csv_file)
    gdf_bndes_periferias.columns = ['nome', 'latitude', 'longitude']
    gdf_bndes_periferias = gpd.GeoDataFrame(gdf_bndes_periferias)
    gdf_bndes_periferias['points_geometry'] = gdf_bndes_periferias.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def cria_df_com_nome_endereco(nome_do_ponto, endereco):
    geolocator = ArcGIS()
    #st.write('trying to geocode')
    location = geolocator.geocode(endereco)
    #st.write('geocode ok!')
    dados_bndes_periferias = {
        'nome': [nome_do_ponto],
        'points_geometry': [Point(location.longitude, location.latitude)]
    }
    gdf_bndes_periferias = gpd.GeoDataFrame(dados_bndes_periferias)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def join_fcus_tipologia(gdf_bndes_periferias):
    # Interseção com tipologia urbanas
    gdf_bndes_periferias_tipologia = gdf_bndes_periferias.sjoin(tipologia,
                                                              how='left',
                                                              predicate='intersects')
    gdf_bndes_periferias_tipologia['GaK'] = gdf_bndes_periferias_tipologia['TipologiaI'].apply(
    lambda x: 'Sim' if (pd.notna(x) and str(x) > 'F') else 'Não')
    # Interseção com FCUs
    gdf_bndes_periferias_tipologia = gdf_bndes_periferias_tipologia.drop(
        columns='index_right', errors='ignore')
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia.sjoin(
        fcus,
        how='left',
        predicate='intersects')
    gdf_bndes_periferias_tipologia_fcus['FCU'] = np.where(
        gdf_bndes_periferias_tipologia_fcus['nm_fcu'].isnull(),
        'Não',
        'Sim')
    return gdf_bndes_periferias_tipologia_fcus

def gera_resultado(gdf_bndes_periferias_tipologia_fcus):
    resultado = gdf_bndes_periferias_tipologia_fcus[['nome', 'NM_MUNICIP', 'TipologiaI', 'GaK', 'nm_fcu', 'FCU']]
    resultado = resultado.rename(columns={'nome': 'Nome',
                                        'NM_MUNICIP': 'Município',
                                        'TipologiaI': 'Tipologia Intraurbana',
                                        'GaK': 'GaK',
                                        'nm_fcu': 'Nome FCU'})
    resultado = resultado.style.applymap(
        lambda v: 'color: red' if v == 'Não' else 'color: green',
        subset=["GaK", "FCU"]
    )
    return resultado

def create_map(gdf_bndes_periferias_tipologia_fcus):
    # Plota tipologias
    tipologia_mapa = gdf_bndes_periferias_tipologia_fcus.set_geometry('tipologia_geometry').dropna(subset=['TipologiaI'])
    m_tipologia = tipologia_mapa.explore('TipologiaI', tooltip=['TipologiaI', 'GaK'], name='Tipologia Intraurbana')

    # Plota fcus
    fcus_mapa = gdf_bndes_periferias_tipologia_fcus.set_geometry('fcus_geometry').dropna(subset=['nm_fcu'])
    m_fcus = fcus_mapa.explore(m=m_tipologia,
                                color='red', tooltip=['nm_fcu'],
                                name='Favelas e Comunidades Urbanas',
                                legend_kwds={'position': 'topright'})

    # Plota pontos
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia_fcus.set_geometry('points_geometry')
    m_pontos = gdf_bndes_periferias_tipologia_fcus.explore(m=m_fcus,
                                                        color='green',
                                                        marker_kwds={'radius': 5},
                                                        style_kwds={'fillOpacity': 1},
                                                        tooltip=['nome'],
                                                        name='Pontos de interesse')
    
    # Add layer control
    folium.LayerControl().add_to(m_pontos)
    return m_pontos    

# --------------------------------------------------------------------------
# INÍCIO DA PÁGINA
# --------------------------------------------------------------------------

st.title("Olá! 🌎")
st.markdown(
    """ 
    Esse é um teste do sistema de cruzamento de pontos de interesse com áreas classificadas como Favelas e Comunidades Urbanas
    ou localizadas em regiões de Tipologia Intraurbana entre G e K.
    """
)

nome_do_ponto = ''
coordenadas = ''
csv_file = ''
latitude = 0.0
longitude = 0.0
endereco = ''

formato = st.radio('Selecione o formato de entrada: ', ['Ponto Individual', 'Arquivo csv'])

if formato == 'Ponto Individual':

    tipo_coord = st.radio('Qual tipo de coordenadas você deseja usar para os pontos?',
            ['Graus, minutos e segundos (DMS)', 
            'Graus decimais',
            'Endereço'])

with st.form("my_form"):    

    if formato == 'Ponto Individual':

        nome_do_ponto = st.text_input(label = 'Insira o nome do ponto ponto a ser analisado:', placeholder='Local A')
        if tipo_coord == 'Graus, minutos e segundos (DMS)':
            coordenadas = st.text_input(label = """Coordenadas: (formato XX°XX'XX.X"S YY°YY'YY.Y"W)""", placeholder = """XX°XX'XX.X"S YY°YY'YY.Y"W""")
        elif tipo_coord == 'Graus decimais':
            latitude = st.number_input(label = 'Latitude', min_value=-90.0, max_value=90.0, format="%0.6f", placeholder=-22.908649345779487)
            longitude = st.number_input(label = 'Longitude', min_value=-180.0, max_value=180.0, format="%0.6f", placeholder=-43.17958239890567)
        elif tipo_coord == 'Endereço':
            endereco = st.text_input(label = 'Endereço')

        # Aqui começa o código para tratar o ponto colocado
        if nome_do_ponto:
            if coordenadas:
                # Carrega dados inputados pelo usuário
                gdf_bndes_periferias = cria_df_com_nome_coord(nome_do_ponto, coordenadas)
            if latitude and longitude:
                gdf_bndes_periferias = cria_df_com_nome_latlon(nome_do_ponto, latitude, longitude)
            if endereco:
                gdf_bndes_periferias = cria_df_com_nome_endereco(nome_do_ponto, endereco)
        
            

    if formato == 'Arquivo csv':
        
        st.write("""O formato esperado do arquivo csv é de três colunas, com cabeçalhos. 
                A primeira coluna deve conter um nome ou identificador para cada ponto analisado, 
                e a segunda e a terceira devem conter a latitude e a longitude (em graus decimais), respectivamente.""")
        csv_file = st.file_uploader("Faça o upload de um arquivo csv:", type='csv')
        if csv_file:
            gdf_bndes_periferias = cria_df_com_csv_latlon(csv_file)
    
    submit = st.form_submit_button('Realizar análise')


if (nome_do_ponto and (coordenadas or (latitude and latitude) or endereco)) or csv_file:
    st.subheader('Dados recebidos')
    dados_recebidos = gdf_bndes_periferias[['nome', 'points_geometry']]
    dados_recebidos['latitude'] = gdf_bndes_periferias['points_geometry'].map(lambda p: p.y)
    dados_recebidos['longitude'] = gdf_bndes_periferias['points_geometry'].map(lambda p: p.x)
    dados_recebidos = dados_recebidos[['nome', 'latitude', 'longitude']]
    st.write(dados_recebidos)
    gdf_bndes_periferias_tipologia_fcus = join_fcus_tipologia(gdf_bndes_periferias)
    
    st.header('Resultado do cruzamento')
    resultado = gera_resultado(gdf_bndes_periferias_tipologia_fcus)
    st.dataframe(resultado)
        
    st.header("Mapa Interativo")
    m = create_map(gdf_bndes_periferias_tipologia_fcus)
    st.write('🟢 Ponto Pesquisado')
    st.write('🟥 Favelas e Comunidades Urbanas')
    st_map = st_folium(m, width=700, height=500)