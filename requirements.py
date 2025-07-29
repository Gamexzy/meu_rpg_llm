import subprocess

def create_requirements_without_versions(output_filename="requirements.txt"):
    """
    Cria um arquivo requirements.txt listando as bibliotecas instaladas
    sem suas versões.
    """
    try:
        # Executa pip freeze e captura a saída
        result = subprocess.run(
            ["pip", "freeze"], capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')

        # Filtra as linhas para remover as versões
        clean_lines = []
        for line in lines:
            if "==" in line:
                package_name = line.split("==")[0]
                clean_lines.append(package_name)
            else:
                clean_lines.append(line) # Adiciona linhas que não possuem == (ex: dependências em modo editável)

        # Escreve as linhas limpas no arquivo
        with open(output_filename, "w") as f:
            for line in sorted(clean_lines): # Opcional: ordenar as bibliotecas
                f.write(line + "\n")
        print(f"Arquivo '{output_filename}' criado com sucesso (sem versões).")

    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar 'pip freeze': {e}")
        print(f"Saída de erro: {e.stderr}")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    create_requirements_without_versions()