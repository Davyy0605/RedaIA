"""Correção de redações com a OpenAI."""
import base64
import json
import os
from pathlib import Path

from openai import OpenAI

# O prompt fica num arquivo de texto para você ajustá-lo sem mexer no código.
PROMPT_SISTEMA = (Path(__file__).parent / "prompt_correcao.txt").read_text(encoding="utf-8")
PROMPT_TRANSCRICAO = (Path(__file__).parent / "prompt_transcricao.txt").read_text(encoding="utf-8")


class ErroCorrecao(Exception):
    """Falha ao obter ou interpretar a correção da IA."""


def _chamar_modelo(sistema: str, usuario, modelo: str | None = None) -> str:
    """`usuario` pode ser texto ou uma lista de partes (texto + imagens) da API da OpenAI."""
    modelo = modelo or os.environ.get("AI_MODEL")
    if not modelo:
        raise ErroCorrecao("Defina a variável AI_MODEL com o modelo da OpenAI.")

    client = OpenAI(timeout=90, max_retries=1)  # lê OPENAI_API_KEY do ambiente
    resp = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        response_format={"type": "json_object"},  # força JSON válido
    )
    return resp.choices[0].message.content or ""


def _extrair_json(texto: str) -> dict:
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim <= inicio:
        raise ErroCorrecao("A resposta da IA não contém JSON.")
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError as e:
        raise ErroCorrecao("JSON inválido na resposta da IA.") from e
    if not isinstance(dados, dict):
        raise ErroCorrecao("Formato inesperado na resposta da IA.")
    return dados


def corrigir_redacao(texto: str, tema: str = "") -> dict:
    """Envia a redação para a IA e devolve o dicionário validado (formato de Competencia.from_json)."""
    # Impede que o aluno "feche" a tag e tente escapar do bloco de texto.
    texto_seguro = texto.replace("</redacao>", "").replace("<redacao>", "")
    tema_seguro = tema.replace("</tema_informado>", "").replace("<tema_informado>", "").strip()

    mensagem = (
        f"<tema_informado>\n{tema_seguro or 'NÃO INFORMADO'}\n</tema_informado>\n\n"
        f"<redacao>\n{texto_seguro}\n</redacao>"
    )
    dados = _extrair_json(_chamar_modelo(PROMPT_SISTEMA, mensagem))

    comps = dados.get("competencias")
    if not isinstance(comps, dict) or not all(
        isinstance(comps.get(f"competencia_{i}"), dict) for i in range(1, 6)
    ):
        raise ErroCorrecao("A resposta da IA veio sem as 5 competências.")
    return dados


def transcrever_imagens(imagens: list[tuple[bytes, str]]) -> dict:
    """Transcreve a redação manuscrita das fotos (em ordem). Recebe [(bytes, mimetype), ...].

    Devolve {"texto": str, "aviso": str}. A transcrição é um rascunho: o aluno revisa antes de enviar.
    """
    partes = [{"type": "text", "text": "Transcreva a redação manuscrita das imagens a seguir."}]
    for conteudo, mimetype in imagens:
        b64 = base64.b64encode(conteudo).decode("ascii")
        partes.append({
            "type": "image_url",
            # "high" é necessário para ler letra cursiva com alguma fidelidade.
            "image_url": {"url": f"data:{mimetype};base64,{b64}", "detail": "high"},
        })

    # Permite usar um modelo diferente (com visão) só para a transcrição.
    modelo = os.environ.get("AI_MODEL_TRANSCRICAO") or os.environ.get("AI_MODEL")
    dados = _extrair_json(_chamar_modelo(PROMPT_TRANSCRICAO, partes, modelo))

    texto = dados.get("texto")
    aviso = dados.get("aviso")
    return {
        "texto": texto.strip() if isinstance(texto, str) else "",
        "aviso": aviso.strip() if isinstance(aviso, str) else "",
    }
