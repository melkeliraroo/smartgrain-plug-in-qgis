import json
from pathlib import Path


class ProjectManager:
    PROJECT_FILE_NAME = "projeto.json"
    PROJECT_DIRECTORIES = (
        "dados_brutos",
        "talhoes",
        "mapas",
        "prescricoes",
        "relatorios",
    )

    def create_project(self, project_dir, data):
        project_path = Path(project_dir)
        project_path.mkdir(parents=True, exist_ok=True)

        for directory_name in self.PROJECT_DIRECTORIES:
            (project_path / directory_name).mkdir(exist_ok=True)

        project_data = {
            "nome": data.get("nome", "").strip(),
            "propriedade": data.get("propriedade", "").strip(),
            "safra": data.get("safra", "").strip(),
            "responsavel": data.get("responsavel", "").strip(),
            "diretorio": str(project_path),
        }

        self._write_project_file(project_path, project_data)
        return project_data

    def open_project(self, project_file):
        project_file_path = Path(project_file)

        with project_file_path.open("r", encoding="utf-8") as file:
            project_data = json.load(file)

        project_data["diretorio"] = str(project_file_path.parent)
        return project_data

    def save_project(self, project_data):
        project_dir = project_data.get("diretorio")

        if not project_dir:
            raise ValueError("O projeto não possui um diretório definido.")

        project_path = Path(project_dir)
        self._write_project_file(project_path, project_data)
        return project_data

    def _write_project_file(self, project_path, project_data):
        project_file_path = project_path / self.PROJECT_FILE_NAME

        with project_file_path.open("w", encoding="utf-8") as file:
            json.dump(project_data, file, ensure_ascii=False, indent=2)
