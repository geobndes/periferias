import streamlit as st
import geopandas as gpd
import folium
from geopy import Point as GeopyPoint
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

def join_fcus_tipologia(gdf_bndes_periferias):
    # Interseção com tipologia urbanas
    gdf_bndes_periferias_tipologia = gdf_bndes_periferias.sjoin(tipologia,
                                                              how='left',
                                                              predicate='intersects')
    gdf_bndes_periferias_tipologia['GaK'] = gdf_bndes_periferias_tipologia['TipologiaI'].apply(
    lambda x: 'Sim' if x >= 'G' else 'Não')
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

def create_map(gdf_bndes_periferias_tipologia_fcus):
    # Plota tipologias
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia_fcus.set_geometry('tipologia_geometry')
    m_tipologia = gdf_bndes_periferias_tipologia_fcus.explore('TipologiaI', tooltip=False, name='Tipologia Intraurbana')

    # Plota fcus
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia_fcus.set_geometry('fcus_geometry')
    m_fcus = gdf_bndes_periferias_tipologia_fcus.explore(m=m_tipologia,
                                                        color='red', tooltip=['nm_fcu'],
                                                        name='Favelas e Comunidades Urbanas',
                                                        legend_kwds={'position': 'topright'})

    # Plota pontos
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia_fcus.set_geometry('points_geometry')
    m_pontos = gdf_bndes_periferias_tipologia_fcus.explore(m=m_fcus,
                                                        color='green',
                                                        marker_kwds={'radius': 5},
                                                        style_kwds={'fillOpacity': 1},
                                                        tooltip=['nome', 'coord_dms', 'NM_MUNICIP', 'TipologiaI', 'GaK', 'nm_fcu'],
                                                        name='Pontos de interesse')
    
    # Add layer control
    folium.LayerControl().add_to(m_pontos)
    return m_pontos    


st.title("Bom dia! 🌎")
st.markdown(
    """ 
    Esse é um teste do sistema de cruzamento de pontos de interesse com áreas classificadas como Favelas e Comunidades Urbanas
    ou localizadas em regiões de Tipologia Intraurbana entre G e K.

    Insira abaixo um nome para o ponto de interesse e suas coordenadas geográficas, no formato indicado.
    """
)

nome_do_ponto = ''
coordenadas = ''
csv_file = ''
formato = st.radio('Selecione o formato de entrada: ', ['Ponto Individual', 'Arquivo csv'])

if formato == 'Ponto Individual':

    nome_do_ponto = st.text_input(label = 'Insira o nome do ponto ponto a ser analisado:')
    coordenadas = st.text_input(label = 'Coordenadas: ', placeholder = """XX°YY'ZZ.Z"S XX°YY'ZZ.Z"W""")

    # Aqui começa o código para tratar o ponto colocado
    if nome_do_ponto and coordenadas:
        # Carrega dados inputados pelo usuário
        gdf_bndes_periferias = cria_df_com_nome_coord(nome_do_ponto, coordenadas)
        

if formato == 'Arquivo csv':
    st.write("""O formato esperado do arquivo csv é de duas colunas, com cabeçalhos. 
             A primeira coluna deve conter um nome ou identificador para cada ponto analisado, 
             e a segunda as coordenadas geográficas em formato XX°YY'ZZ.Z"S XX°YY'ZZ.Z"W""")
    csv_file = st.file_uploader("Faça o upload de um arquivo csv:", type='csv')
    if csv_file:
        gdf_bndes_periferias = pd.read_csv(csv_file)
        gdf_bndes_periferias.columns = ['nome', 'coord_dms']
        gdf_bndes_periferias = gpd.GeoDataFrame(gdf_bndes_periferias)
        gdf_bndes_periferias['points_geometry'] = gdf_bndes_periferias['coord_dms'].map(dms_to_point)
        gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
        gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')


if (nome_do_ponto and coordenadas) or csv_file:
    st.subheader('Dados recebidos')
    st.write(gdf_bndes_periferias)
    gdf_bndes_periferias_tipologia_fcus = join_fcus_tipologia(gdf_bndes_periferias)
    resultado = gdf_bndes_periferias_tipologia_fcus[['nome', 'coord_dms', 'NM_MUNICIP', 'TipologiaI', 'GaK', 'nm_fcu', 'FCU']]
    resultado = resultado.rename(columns={'nome': 'Nome',
                                        'coord_dms': 'Coordenadas',
                                        'NM_MUNICIP': 'Município',
                                        'TipologiaI': 'Tipologia Intraurbana',
                                        'GaK': 'GaK',
                                        'nm_fcu': 'Nome FCU'})
    st.header('Resultado do cruzamento')
    st.write(resultado)
        
    st.header("Mapa Interativo")
    m = create_map(gdf_bndes_periferias_tipologia_fcus)
    st.write('🟢 Ponto Pesquisado')
    st.write('🟥 Favelas e Comunidades Urbanas')
    st_map = st_folium(m, width=700, height=500)