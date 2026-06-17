import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / 'data'
SOURCE_PATH = DATA_DIR / 'ai_hub_data/test/01. source/AS20240324_S_P0001_T001.json'
LABEL_PATH = DATA_DIR / 'ai_hub_data/test/02. label/AS20240324_T_P0001_T001.json'
OUT_PATH = DATA_DIR / 'processed/incidents.json'


def main() -> None:
    source = json.loads(SOURCE_PATH.read_text())
    label = json.loads(LABEL_PATH.read_text())

    incident = {
        'incident_id': source['raw_data_info']['fire_info']['fire_incident_id'],
        'region': source['raw_data_info']['fire_info']['region'],
        'lat': source['raw_data_info']['fire_info']['fire_location']['lat'],
        'lon': source['raw_data_info']['fire_info']['fire_location']['lon'],
        'user_type': source['source_data_info']['user_info']['user_type_description'],
        'risk_features': {
            'temperature': source['source_data_info']['weather_conditions']['temperature'],
            'humidity_percent': source['source_data_info']['weather_conditions']['humidity_percent'],
            'wind_speed': source['source_data_info']['weather_conditions']['wind_speed'],
            'slope': source['source_data_info']['terrain_conditions']['slope'],
            'fuel_moisture': source['source_data_info']['fuel_conditions']['fuel_moisture'],
            'vulnerable': source['source_data_info']['Infra_Social']['vulnerable'],
        },
        'label_metadata': {
            'query_purpose': label['labelling_data_info']['query']['query_purpose'],
            'query_subject': label['labelling_data_info']['query']['query_subject'],
            'query_type': label['labelling_data_info']['query']['query_type'],
            'root_confidence': label['labelling_data_info']['tree_of_thought']['level_0_input']['L0_confidence_score'],
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps([incident], ensure_ascii=False, indent=2))
    print(f'Wrote 1 incident to {OUT_PATH}')


if __name__ == '__main__':
    main()
