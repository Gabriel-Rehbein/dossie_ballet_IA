
from flask import Flask, render_template, request, make_response
import json, re, io
from dataclasses import dataclass, field
from typing import Dict, Any, List

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me"

# -------- LLM mock --------
def llm_local(prompt: str) -> str:
    p = prompt.lower()
    if "curar programa" in p:
        return (
            "Programa Sugerido:\n"
            "Ato I: 'O Lago dos Cisnes' – Trechos do Ato II (Tchaikovsky)\n"
            "Ato II: 'A Bela Adormecida' – Variação Florine e Pássaro Azul (Tchaikovsky)\n"
            "Ato III: 'Dom Quixote' – Grand Pas de Deux (Minkus)\n"
            "Justificativa geral: equilíbrio entre lirismo e virtuosismo; trechos populares."
        )
    if "escrever release" in p:
        return (
            "Release:\n"
            "A temporada ‘Clássicos em Cena’ celebra o legado do ballet acadêmico com três atos icônicos, "
            "unindo a poesia de Tchaikovsky e a energia de Minkus. Solistas convidados e cenografia modular "
            "garantem uma experiência imersiva ao público. Duração aprox.: 95 min."
        )
    if "cronograma técnico" in p:
        return (
            "Cronograma Técnico (base):\n"
            "- Montagem/linóleo: 10:00–12:00\n"
            "- Luz & presets: 12:00–14:30\n"
            "- Marcação: 14:30–15:00\n"
            "- Ensaios: 15:00–17:00\n"
            "- Passagem geral: 17:15–18:30\n"
            "- Abertura de portas: 19:30\n"
            "- Espetáculo: 20:00"
        )
    return "OK"

LLM = llm_local

# -------- Núcleo multiagente --------
@dataclass
class Agent:
    name: str
    role: str
    goal: str
    backstory: str
    def run(self, task_prompt: str, memory: Dict[str, Any]) -> str:
        return LLM(task_prompt)

@dataclass
class Task:
    title: str
    owner: Agent
    prompt_template: str
    write_key: str
    depends_on: List[str] = field(default_factory=list)
    def execute(self, memory: Dict[str, Any]) -> None:
        if any(dep not in memory for dep in self.depends_on):
            return
        filled = self.prompt_template.format(**memory)
        memory[self.write_key] = self.owner.run(filled, memory)

@dataclass
class Crew:
    agents: Dict[str, Agent]
    tasks: List[Task]
    memory: Dict[str, Any] = field(default_factory=dict)
    def run(self) -> Dict[str, Any]:
        for t in self.tasks:
            t.execute(self.memory)
        return self.memory

# -------- Parser & implicações --------
def parse_dados_publico(texto: str) -> Dict[str, Any]:
    t = texto.lower()

    comp_pref = {}
    for nome in ["tchaikovsky", "minkus", "adam", "prokofiev", "glazunov"]:
        m1 = re.search(rf"(\d+)\s*%\s*{nome}", t)
        m2 = re.search(rf"{nome}.*?(\d+)\s*%", t)
        pct = int(m1.group(1)) if m1 else (int(m2.group(1)) if m2 else None)
        if pct is not None:
            comp_pref[nome.capitalize()] = max(0, min(100, pct))

    m_h = re.search(r"\b(\d{1,2})(?:(?:h|hs)|:(\d{2}))\b", t)
    horario = None
    if m_h:
        h = int(m_h.group(1)); m = int(m_h.group(2) or 0)
        if 0 <= h <= 23 and 0 <= m <= 59:
            horario = f"{h:02d}:{m:02d}"

    dias_map = {
        "segunda":"segunda", "terça":"terça", "terca":"terça", "quarta":"quarta",
        "quinta":"quinta", "sexta":"sexta", "sábado":"sábado", "sabado":"sábado", "domingo":"domingo"
    }
    dia_pref = None
    for raw, norm in dias_map.items():
        if raw in t: dia_pref = norm; break

    m_age = re.search(r"\b(\d{1,2})\s*[–-]\s*(\d{1,2})\b", t)
    faixa = None
    if m_age:
        a, b = int(m_age.group(1)), int(m_age.group(2))
        if 0 < a <= b <= 120: faixa = f"{a}–{b}"

    canais = [c for c in ["instagram", "reels", "tiktok", "youtube", "facebook", "whatsapp"] if c in t]
    preco_sensivel = any(k in t for k in ["preço","preco","caro","barato","meia-entrada","estudante"])

    return {
        "preferencias_compositores": comp_pref,
        "dia_preferido": dia_pref,
        "horario_preferido": horario,
        "faixa_etaria": faixa,
        "canais": canais,
        "preco_sensivel": preco_sensivel
    }

def derivar_implicacoes(aud: Dict[str, Any]) -> Dict[str, Any]:
    horario = aud.get("horario_preferido") or "20:00"
    dia = aud.get("dia_preferido") or "sábado"
    janela_show = f"{dia} às {horario}"

    comp = aud.get("preferencias_compositores", {})
    top = sorted(comp.items(), key=lambda x: x[1], reverse=True)
    destaques = [n for n, _ in top[:2]] if top else ["Tchaikovsky", "Minkus"]

    faixa = aud.get("faixa_etaria")
    tom = "visual dinâmico, cortes rápidos e linguagem direta" if faixa else "linguagem acolhedora e foco em tradição"
    canais = aud.get("canais") or ["instagram", "reels"]
    preco = "destacar meia-entrada/combos" if aud.get("preco_sensivel") else "valor artístico e experiência imersiva"

    return {
        "janela_show": janela_show,
        "compositores_prioritarios": destaques,
        "tom_comunicacao": tom,
        "canais_prioritarios": canais,
        "estrategia_preco": preco
    }

# -------- Agentes & Tasks --------
curador = Agent("Curador", "Definir repertório", "Montar programa coerente e popular", "Especialista em repertório clássico.")
redator = Agent("Redator", "Comunicação", "Escrever release alinhado ao público", "Jornalista cultural de dança.")
diretor = Agent("Diretor Técnico", "Palco e ensaios", "Planejar cronograma otimizado", "Stage manager experiente.")
avaliador = Agent("Avaliador de Coerência", "Validação", "Relacionar dados do público às decisões", "Consultor de market-fit.")

tasks = [
    Task("Curar Programa", curador,
         "Curar Programa — considerar preferências como referência.\nAudiência:\n{audiencia_struct}\n",
         "programa_classico"),
    Task("Escrever Release", redator,
         "Escrever Release — usar programa + audiência + implicações.\n"
         "Programa:\n{programa_classico}\n\nAudiência:\n{audiencia_struct}\n\nImplicações:\n{implicacoes}\n",
         "release_press", depends_on=["programa_classico","audiencia_struct","implicacoes"]),
    Task("Cronograma Técnico", diretor,
         "Cronograma Técnico — ajustar abertura para a janela recomendada.\n"
         "Programa:\n{programa_classico}\nJanela: {janela_show}\n",
         "cronograma_tecnico", depends_on=["programa_classico","janela_show"]),
    Task("Relacionar", avaliador,
         "Relacionar — explique como dados -> decisões.\n"
         "Dados brutos:\n{dados_publico}\n\nAudiência:\n{audiencia_struct}\n\nImplicações:\n{implicacoes}\n\n"
         "Programa:\n{programa_classico}\n\nRelease:\n{release_press}\n\nCronograma:\n{cronograma_tecnico}\n",
         "relacao_dados_respostas",
         depends_on=["programa_classico","release_press","cronograma_tecnico","audiencia_struct","implicacoes"]),
]

# -------- Helpers de export --------
def build_markdown(mem: Dict[str, Any]) -> str:
    parts = [
        "# Dossiê – Ballet Clássico",
        "## Programa", mem.get("programa_classico","").strip(),
        "## Release", mem.get("release_press","").strip(),
        "## Cronograma Técnico", mem.get("cronograma_tecnico","").strip(),
        "## Relação entre Dados do Público e Decisões", mem.get("relacao_dados_respostas","").strip(),
        "## Dados do Público (Bruto)", mem.get("dados_publico","").strip(),
        "## Audiência (Estruturado)", "```json\n" + mem.get("audiencia_struct","{}") + "\n```",
        "## Implicações", "```json\n" + mem.get("implicacoes","{}") + "\n```",
    ]
    return "\n\n".join(parts).strip()+"\n"

# -------- Rotas --------
@app.get("/")
def index():
    return render_template("index.html")

@app.post("/gerar")
def gerar():
    dados_publico = request.form.get("dados_publico","").strip()
    if not dados_publico:
        return render_template("index.html", error="Digite os dados do público.")

    aud = parse_dados_publico(dados_publico)
    implic = derivar_implicacoes(aud)

    memoria: Dict[str, Any] = {
        "dados_publico": dados_publico,
        "audiencia_struct": json.dumps(aud, ensure_ascii=False, indent=2),
        "implicacoes": json.dumps(implic, ensure_ascii=False, indent=2),
        "janela_show": implic["janela_show"],
        "tema": "Espetáculos de Ballet Clássico",
        "funcao": ("Gerar dossiê com programa, release, cronograma técnico, "
                   "alinhados aos dados de público."),
    }

    crew = Crew(
        agents={a.name: a for a in [curador, redator, diretor, avaliador]},
        tasks=tasks,
        memory=memoria
    )
    crew.run()

    # Para downloads
    json_payload = json.dumps({
        k: memoria.get(k,"") for k in [
            "programa_classico","release_press","cronograma_tecnico",
            "relacao_dados_respostas","dados_publico","audiencia_struct","implicacoes","janela_show"
        ]
    }, ensure_ascii=False, indent=2)
    md_payload = build_markdown(memoria)

    return render_template("result.html",
                           programa=memoria.get("programa_classico",""),
                           release=memoria.get("release_press",""),
                           cronograma=memoria.get("cronograma_tecnico",""),
                           relacao=memoria.get("relacao_dados_respostas",""),
                           dados_publico=dados_publico,
                           audiencia_struct=memoria["audiencia_struct"],
                           implicacoes=memoria["implicacoes"],
                           json_payload=json_payload,
                           md_payload=md_payload)

@app.post("/download/json")
def download_json():
    data = request.form.get("json_payload","{}")
    buf = io.BytesIO(data.encode("utf-8"))
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=dossie_ballet.json"
    return resp

@app.post("/download/md")
def download_md():
    data = request.form.get("md_payload","# Dossiê – Ballet Clássico\n")
    buf = io.BytesIO(data.encode("utf-8"))
    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=dossie_ballet.md"
    return resp

if __name__ == "__main__":
    app.run(debug=True)
