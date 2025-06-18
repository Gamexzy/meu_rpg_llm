import json
import re
import os

def convert_glossary_md_to_json(md_path, json_path):
    glossary_terms = []
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex para encontrar itens de lista Markdown que representam termos
    # Assume que cada termo começa com um marcador de lista e a definição segue.
    # Pode precisar de ajuste fino dependendo da formatação exata do seu MD.
    # Ex: - **Termo**: Definição ou * Termo: Definição
    # Esta regex busca linhas que começam com um marcador de lista e que contêm ':'
    entries = re.findall(r'^[*-]\s*\*\*?(.+?)\*\*?\s*:\s*(.+?)(?=\n[*-]|\n\n|\Z)', content, re.MULTILINE | re.DOTALL)

    if not entries:
        # Tenta outra regex se a primeira falhar (ex: sem negrito)
        entries = re.findall(r'^[*-]\s*([^:]+?)\s*:\s*(.+?)(?=\n[*-]|\n\n|\Z)', content, re.MULTILINE | re.DOTALL)


    for term_match, definition_match in entries:
        glossary_terms.append({
            "termo": term_match.strip(),
            "definicao": definition_match.strip()
        })

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(glossary_terms, f, ensure_ascii=False, indent=2)
    print(f"Glossário convertido de {md_path} para {json_path}")

if __name__ == "__main__":
    md_file = "documentos_rpg_md/Documento RPG - Glossário de Termos.md"
    json_file = "dados_estruturados/lore_estatica/glossario.json"

    # Garante que a pasta de destino exista
    os.makedirs(os.path.dirname(json_file), exist_ok=True)

    convert_glossary_md_to_json(md_file, json_file)