import streamlit as st
import geopandas as gpd
import folium
from geopy import Point as GeopyPoint
from geopy.geocoders import ArcGIS
from shapely.geometry import Point
from streamlit_folium import st_folium
import numpy as np
import pandas as pd
import zipfile
import tempfile
import os

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

def cria_df_com_dict(dict):
    # O dict esperado dois pares chave-valor: um com nomes para os pontos e outros com shapely Points
    gdf_bndes_periferias = gpd.GeoDataFrame(dict)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def cria_df_com_csv_latlon(csv_file, tem_header):
    header_option = 'infer' if tem_header else None
    gdf_bndes_periferias = pd.read_csv(csv_file, header=header_option)
    gdf_bndes_periferias.columns = ['nome', 'latitude', 'longitude']
    gdf_bndes_periferias = gpd.GeoDataFrame(gdf_bndes_periferias)
    gdf_bndes_periferias['points_geometry'] = gdf_bndes_periferias.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
    gdf_bndes_periferias = gdf_bndes_periferias.set_geometry('points_geometry')
    gdf_bndes_periferias = gdf_bndes_periferias.set_crs('epsg:4674')
    return gdf_bndes_periferias

def cria_df_com_shp_zip(uploaded_zip_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the uploaded .zip
        zip_path = os.path.join(tmpdir, "shapefile.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip_file.read())
        
        # Extract the zip file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # List of extracted files
        extracted_files = os.listdir(tmpdir)
        markdown_extracted_files = [f"- :blue-background[{f}]  " for f in extracted_files]
        st.write("Arquivos extraídos: ")
        for item in markdown_extracted_files:
            st.markdown(item)

        # Find the base name
        shp_files = [f for f in extracted_files if f.endswith('.shp')]
        if not shp_files:
            st.error("Nenhum arquivo .shp encontrado")
        else:
            basename = os.path.splitext(shp_files[0])[0]
            required_exts = ['.shp', '.shx', '.dbf', '.prj']
            missing_files = [f"{basename}{ext}" for ext in required_exts if f"{basename}{ext}" not in extracted_files]

            if missing_files:
                st.error(f"Faltando componentes obrigatórios do shapefile: {missing_files}")    
            else: 
                try:
                    shp_path = os.path.join(tmpdir, f"{basename}.shp")
                    gdf = gpd.read_file(shp_path)
                    st.success("Shapefile lido com sucesso!")
                    gdf['nome'] = gdf.index.to_series().apply(lambda x: f"Entrada {x+1}")
                    return gdf
                except Exception as e:
                    st.error(f"Falha ao ler shapefile: {e}")

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
    gdf_bndes_periferias_tipologia_fcus = gdf_bndes_periferias_tipologia_fcus.reset_index()
    return gdf_bndes_periferias_tipologia_fcus

def gera_resultado(gdf_bndes_periferias_tipologia_fcus):
    resultado = gdf_bndes_periferias_tipologia_fcus[['nome', 'NM_MUNICIP', 'TipologiaI', 'GaK', 'nm_fcu', 'FCU']]
    resultado = resultado.rename(columns={'nome': 'Nome',
                                        'NM_MUNICIP': 'Município',
                                        'TipologiaI': 'Tipologia Intraurbana',
                                        'GaK': 'GaK',
                                        'nm_fcu': 'Nome FCU'})
    return resultado

def gera_resultado_com_geometria_shp(gdf_bndes_periferias_tipologia_fcus):
    resultado = gdf_bndes_periferias_tipologia_fcus[['nome', 'geometry', 'tipologia_geometry', 'fcus_geometry', 'NM_MUNICIP', 'TipologiaI', 'GaK', 'nm_fcu', 'FCU']]
    return resultado

def style_resultado(df):
    df = df.style.applymap(
        lambda v: 'color: red' if v == 'Não' else 'color: green',
        subset=["GaK", "FCU"]
    )
    return df

def create_map(gdf, geom_type='points'):
    # Espera que o gfd tenha certas colunas. Mudar para lógica com variáveis
    
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    sw = [bounds[1], bounds[0]]
    ne = [bounds[3], bounds[2]]
    # Plota tipologias
    tipologia_mapa = gdf.set_geometry('tipologia_geometry').dropna(subset=['TipologiaI'])
    m_tipologia = tipologia_mapa.explore('TipologiaI', tooltip=['TipologiaI', 'GaK'], name='Tipologia Intraurbana', legend=True)

    # Plota fcus
    fcus_mapa = gdf.set_geometry('fcus_geometry').dropna(subset=['nm_fcu'])
    m_fcus = fcus_mapa.explore(m=m_tipologia,
                                color='red', tooltip=['nm_fcu'],
                                name='Favelas e Comunidades Urbanas')

    if geom_type == 'points':
        # Plota pontos
        gdf = gdf.set_geometry('points_geometry')
        m_pontos = gdf.explore(m=m_fcus,
                                                            color='green',
                                                            marker_kwds={'radius': 5},
                                                            style_kwds={'fillOpacity': 1},
                                                            tooltip=['nome'],
                                                            name='Pontos de interesse')
        
    if geom_type == 'shapes':
        # Plota pontos
        gdf = gdf.set_geometry('geometry')
        m_pontos = gdf.explore(m=m_fcus,
                                                            color='green',
                                                            name='Shapes de interesse')

    
    # Add layer control
    folium.LayerControl().add_to(m_pontos)
    m_pontos.fit_bounds([sw, ne])
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

# Inicialização de variáveis de input
nome_do_ponto = ''
coordenadas = ''
csv_file = ''
uploaded_zip_files = []
latitude = 0.0
longitude = 0.0
endereco = ''
gdf_bndes_periferias = None
input_data = {}

formato = st.radio('Selecione o formato de entrada: ', ['Ponto Individual', 'Arquivo csv', 'Shapefile'])

if formato == 'Ponto Individual':

    if "input_count" not in st.session_state:
        st.session_state.input_count = 1

    tipo_coord = st.radio('Qual tipo de coordenadas você deseja usar para os pontos?',
            ['Graus decimais',
             'Graus, minutos e segundos (DMS)'])
    
    if formato == 'Ponto Individual':
        col_mais, col_menos, col_empty = st.columns([1,1, 1])
        if col_mais.button("➕ Adicionar novo ponto"):
            st.session_state.input_count += 1
        if col_menos.button("❌ Remover ponto") and st.session_state.input_count > 1:
            st.session_state.input_count -= 1

with st.form("my_form"):    

    if formato == 'Ponto Individual':
        input_data = {'nome': [], 'points_geometry': []}
        for i in range(st.session_state.input_count):
            col1, col2 = st.columns([1,2], vertical_alignment='bottom')
            nome_do_ponto = col1.text_input(label = 'Nome do ponto:', placeholder='Local A', key=f"nome_{i}")
            input_data['nome'].append(nome_do_ponto)
            if tipo_coord == 'Graus, minutos e segundos (DMS)':
                coordenadas = col2.text_input(label = """Coordenadas: (formato XX°XX'XX.X"S YY°YY'YY.Y"W)""", 
                                              placeholder = """XX°XX'XX.X"S YY°YY'YY.Y"W""",
                                              key = f"coord_dms_{i}")
                if coordenadas:
                    try:
                        input_data['points_geometry'].append(dms_to_point(coordenadas))
                    except Exception as e:
                        st.error(f"Falha ao tratar as coordenadas fornecidas. Verifique o formato da entrada. Erro: {e}")
            elif tipo_coord == 'Graus decimais':
                col21, col22 = col2.columns([1,1], vertical_alignment='bottom')
                latitude = col21.number_input(label = 'Latitude', min_value=-90.0, max_value=90.0, format="%0.6f", 
                                              placeholder=-22.908649345779487,
                                              key = f"latitude_{i}")
                longitude = col22.number_input(label = 'Longitude', min_value=-180.0, max_value=180.0, format="%0.6f", 
                                               placeholder=-43.17958239890567,
                                               key = f"longitude_{i}")
                input_data['points_geometry'].append(Point(longitude, latitude))

    if formato == 'Arquivo csv':
        
        st.write("""O formato esperado do arquivo csv é de três colunas. 
                A primeira coluna deve conter um nome ou identificador para cada ponto analisado, 
                e a segunda e a terceira devem conter a latitude e a longitude (em graus decimais), respectivamente.""")
        tem_header = st.checkbox('Meu arquivo tem uma primeira linha de cabeçalhos')    
        csv_file = st.file_uploader("Faça o upload de um arquivo csv:", type='csv')
        

    if formato == 'Shapefile':

        st.write("""Faça o upload de um ou mais zips com todos os arquivos componentes de um shapefile. Os arquivos dentro de cada zip devem ter todos
                 o mesmo nome, e são necessários, no mínimos, os arquivos de extensão .shp, .shx, .dbf e.prj.""")
        uploaded_zip_files = st.file_uploader("Faça o upload de um arquivo zip:", type='zip', accept_multiple_files=True)

    submit = st.form_submit_button('Realizar análise')


if (nome_do_ponto and (coordenadas or (latitude and latitude) or endereco)) or csv_file:
    if (nome_do_ponto and (coordenadas or (latitude and latitude) or endereco)):
        gdf_bndes_periferias = cria_df_com_dict(input_data)
    if csv_file:
            gdf_bndes_periferias = cria_df_com_csv_latlon(csv_file, tem_header)
    st.subheader('Dados recebidos')
    dados_recebidos = gdf_bndes_periferias[['nome', 'points_geometry']]
    dados_recebidos['latitude'] = gdf_bndes_periferias['points_geometry'].map(lambda p: p.y)
    dados_recebidos['longitude'] = gdf_bndes_periferias['points_geometry'].map(lambda p: p.x)
    dados_recebidos = dados_recebidos[['nome', 'latitude', 'longitude']]
    st.write(dados_recebidos)
    gdf_bndes_periferias_tipologia_fcus = join_fcus_tipologia(gdf_bndes_periferias)
    
    st.header('Resultado do cruzamento')
    resultado = gera_resultado(gdf_bndes_periferias_tipologia_fcus)
    st.dataframe(style_resultado(resultado))
        
    st.header("Mapa Interativo")
    st.write('🟢 Ponto Pesquisado')
    st.write('🟥 Favelas e Comunidades Urbanas')
    m = create_map(gdf_bndes_periferias_tipologia_fcus, geom_type='points')
    st_map = st_folium(m, width=700, height=500)

elif uploaded_zip_files:
    gdf_bndes_periferias_list = [] # list of geodataframes
    for zip_file in uploaded_zip_files:
        gdf_bndes_periferias_list.append(cria_df_com_shp_zip(zip_file))
    st.subheader('Dados recebidos')
    resultados = [] # list of dataframes
    resultados_mapa = []
    for gdf in gdf_bndes_periferias_list:
        dados_recebidos = gdf
        st.write(dados_recebidos)   
        gdf_bndes_periferias_tipologia_fcus = join_fcus_tipologia(gdf)
        resultados.append(gera_resultado(gdf_bndes_periferias_tipologia_fcus))
        resultados_mapa.append(gera_resultado_com_geometria_shp(gdf_bndes_periferias_tipologia_fcus))
    st.header('Resultado do cruzamento')
    resultado = pd.concat(resultados, ignore_index=True)
    st.dataframe(style_resultado(resultado))

    st.header("Mapa Interativo")
    st.write('🟢 Ponto Pesquisado')
    st.write('🟥 Favelas e Comunidades Urbanas')
    resultado_mapa = gpd.GeoDataFrame(pd.concat(resultados_mapa, ignore_index=True), crs=resultados_mapa[0].crs)
    m = create_map(resultado_mapa, geom_type='shapes')
    st_map = st_folium(m, width=700, height=500)