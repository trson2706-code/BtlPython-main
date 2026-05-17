import yaml
import os

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Không tìm thấy file config tại {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._data = yaml.safe_load(f)

    def get(self, *keys, default=None):
        """
        Lấy giá trị từ config theo keys lồng nhau.
        VD: Config().get('camera', 'fps')
        """
        val = self._data
        for key in keys:
            if isinstance(val, dict) and key in val:
                val = val[key]
            else:
                return default
        return val

# Sử dụng: config = Config()
