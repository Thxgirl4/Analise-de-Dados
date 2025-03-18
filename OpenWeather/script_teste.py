import json
import pandas as pd
import requests

url = "https://api.openweathermap.org/data/2.5/forecast"
params = {"q": "Bagé", "appid":"23c492dbc5bb9b3e9ad4e6d15029b6e4", "units": "metric", "lang": "pt"}



resposta = requests.get(url, params=params)

if resposta.status_code != 200:
    print(f"Erro na requisição: {resposta.status_code} - {resposta.text}")
    exit()

try:
    requisicao_dic = resposta.json()
except requests.exceptions.JSONDecodeError:
    print("Erro: A resposta da API não é um JSON válido!")
    print("Resposta recebida: ", resposta.text)
    exit()

dado = requisicao_dic.get("list", [])

dados_list = [] #variavel para armazenar os dados que queremos em uma lista
for dict_item in dado: #laço for para percorrer todas as informações contidas na variavel dados
  temp_min = dict_item['main']['temp_min'] #armazenando as informações de temperatura minima
  temp_max = dict_item['main']['temp_max']  #armazenando as informações de temperatura maxima
  desc = dict_item['weather'][0]['description'] #armazenando as informações de descrição
  data = dict_item["dt_txt"] #armazenando as informações de datas e horarios
  wind = dict_item["wind"] #armazenando as informações de vento

  wind['Temp_min'] = f"{int(temp_min)}" #atualizando o dicionario wind e adicionando as informações de temperatura minima
  wind['Temp_max'] = f"{int(temp_max)}" ##atualizando o dicionario wind e adicionando as informações de temperatura maxima
  wind['Descricao'] = desc #atualizando o dicionario wind e adicionando as informações de descrição
  wind['Data'] = data.replace(':', "H").replace('-', '/') #atualizando o dicionario wind e adicionando as informações de data e horario
  dados_list.append(wind) #incrementando os dados de wind na lista vazia dados_list

dados_df = pd.DataFrame(dados_list, columns=['speed', 'deg', 'gust', 'Temp_min', 'Temp_max', 'Descricao', 'Data'])
dados_df = dados_df.rename(columns={'speed': 'Vel_Km/h', 'deg': 'Direcao', 'gust': 'Rajada_Km/h' })

dados_df['Vel_Km/h'] = (dados_df['Vel_Km/h'] * 3.6).round()
dados_df['Rajada_Km/h'] = (dados_df['Rajada_Km/h'] * 3.6).round()
pd.set_option('display.expand_frame_repr', False)
dados_df.to_csv("previsao_tempoBG2.csv", index=False, encoding='utf-8', sep=";")