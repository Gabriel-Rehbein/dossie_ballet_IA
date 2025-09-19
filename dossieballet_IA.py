# main.py
# Sistema Multiagente: Espetáculos de Ballet Clássico
# Foco agora: UX no console (menu, validação, edição, salvar/abrir)

import re, json, os, sys
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# =========================
# UI Helpers (sem dependências)
# =========================
class UI:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    OK = "\033[32m"
    WARN = "\033[33m"
    ERR = "\033[31m"
    RESET = "\033[0m"

    @staticmethod
    def print_h1(text: str):
        print(f"\n{UI.BOLD}{text}{UI.RESET}")

    @staticmethod
    def ask(prompt: str) -> str:
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            print(f"\n{UI.ERR}Entrada cancelada.{UI.RESET}")
            sys.exit(1)

    @staticmethod
    def ask_yesno(prompt: str, default: bool = True) -> bool:
        suf = "[S/n]" if default else "[s/N]"
        while True:
            ans = UI.ask(f"{prompt} {suf} ").strip().lower()
            if not ans:
                return default
            if ans in ("s", "sim", "y", "yes"): return True
            if ans in ("n", "nao", "não", "no"): return False
            print(f"{UI.WARN}Responda s/n.{UI.RESET}")

    @staticmethod
    def ask_multiline(prompt: str, end_token: str = "fim") -> str:
        print(f"{prompt} ({UI.DIM}Digite '{end_token}' numa linha para finalizar{UI.RESET})")
        lines = []
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{UI.ERR}Entrada cancelada.{UI.RESET}")
                sys.exit(1)
            if line.strip().lower() == end_token:
                break
            lines.append(line)
        return "\n".join(lines).strip()

# =========================
# LLM local (mock)
# =========================
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

# =========================
# Núcleo Multiagente
# =========================
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

# =========================
# Parser + Implicações
# =========================
def parse_dados_publico(texto: str) -> Dict[str, Any]:
    t = texto.lower()

    comp_pref = {}
    for nome in ["tchaikovsky", "minkus", "adam", "prokofiev", "glazunov"]:
        m1 = re.search(rf"(\d+)\s*%\s*{nome}", t)
        m2 = re.search(rf"{nome}.*?(\d+)\s*%", t)
        pct = int(m1.group(1)) if m1 else (int(m2.group(1)) if m2 else None)
        if pct is not None:
            comp_pref[nome.capitalize()] = max(0, min(100, pct))

    # Horário (20h, 20:00, 20hs → HH:MM)
    m_h = re.search(r"\b(\d{1,2})(?:(?:h|hs)|:(\d{2}))\b", t)
    horario = None
    if m_h:
        h = int(m_h.group(1))
        m = int(m_h.group(2) or 0)
        if 0 <= h <= 23 and 0 <= m <= 59:
            horario = f"{h:02d}:{m:02d}"

    # Dia
    dias_map = {
        "segunda":"segunda", "terça":"terça", "terca":"terça", "quarta":"quarta",
        "quinta":"quinta", "sexta":"sexta", "sábado":"sábado", "sabado":"sábado", "domingo":"domingo"
    }
    dia_pref = None
    for raw, norm in dias_map.items():
        if raw in t: dia_pref = norm; break

    # Faixa etária 18–34 / 18-35
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

# =========================
# Agentes e Tasks
# =========================
curador = Agent("Curador", "Definir repertório", "Montar programa coerente e popular", "Especialista em repertório clássico.")
redator = Agent("Redator", "Comunicação", "Escrever release alinhado ao público", "Jornalista cultural de dança.")
diretor = Agent("Diretor Técnico", "Palco e ensaios", "Planejar cronograma otimizado", "Stage manager experiente.")
avaliador = Agent("Avaliador de Coerência", "Validação", "Relacionar dados do público às decisões", "Consultor de market-fit.")

tasks = [
    Task("Curar Programa", curador,
         "Curar Programa — considerar preferências como referência.\n"
         "Audiência:\n{audiencia_struct}\n", "programa_classico"),
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

# =========================
# Persistência
# =========================
def salvar_json(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def carregar_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_md(path: str, memoria: Dict[str, Any]):
    md = [
        "# Dossiê – Ballet Clássico",
        "## Programa", memoria.get("programa_classico","").strip(),
        "## Release", memoria.get("release_press","").strip(),
        "## Cronograma Técnico", memoria.get("cronograma_tecnico","").strip(),
        "## Relação entre Dados do Público e Decisões", memoria.get("relacao_dados_respostas","").strip(),
        "## Dados do Público (Bruto)", memoria.get("dados_publico","").strip(),
        "## Audiência (Estruturado)", "```json\n" + memoria.get("audiencia_struct","{}") + "\n```",
        "## Implicações", "```json\n" + memoria.get("implicacoes","{}") + "\n```",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(md).strip()+"\n")

# =========================
# Menu / Fluxo
# =========================
def menu() -> None:
    memoria: Dict[str, Any] = {}
    crew = Crew(
        agents={a.name: a for a in [curador, redator, diretor, avaliador]},
        tasks=tasks,
        memory=memoria
    )

    while True:
        UI.print_h1("=== Sistema Multiagente: Ballet Clássico ===")
        print("1) Digitar/colar DADOS DO PÚBLICO (multi-linha)")
        print("2) Carregar DADOS DO PÚBLICO de arquivo .txt/.md/.json")
        print("3) Ver/Editar audiência estruturada (JSON)")
        print("4) Gerar DOSSIÊ")
        print("5) Salvar resultados (Markdown/JSON)")
        print("6) Sair")

        op = UI.ask("\nEscolha uma opção: ").strip()
        if op == "1":
            texto = UI.ask_multiline("Cole/Escreva os dados do público", end_token="fim")
            aud = parse_dados_publico(texto)
            implic = derivar_implicacoes(aud)
            memoria.update({
                "dados_publico": texto,
                "audiencia_struct": json.dumps(aud, ensure_ascii=False, indent=2),
                "implicacoes": json.dumps(implic, ensure_ascii=False, indent=2),
                "janela_show": implic["janela_show"],
            })
            print(f"{UI.OK}Dados do público capturados e estruturados.{UI.RESET}")

        elif op == "2":
            path = UI.ask("Caminho do arquivo (.txt/.md/.json): ").strip()
            if not os.path.isfile(path):
                print(f"{UI.ERR}Arquivo não encontrado.{UI.RESET}")
                continue
            if path.lower().endswith(".json"):
                try:
                    data = carregar_json(path)
                    texto = data.get("dados_publico","")
                except Exception as e:
                    print(f"{UI.ERR}Falha ao ler JSON: {e}{UI.RESET}")
                    continue
            else:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        texto = f.read()
                except Exception as e:
                    print(f"{UI.ERR}Falha ao ler arquivo: {e}{UI.RESET}")
                    continue

            aud = parse_dados_publico(texto)
            implic = derivar_implicacoes(aud)
            memoria.update({
                "dados_publico": texto,
                "audiencia_struct": json.dumps(aud, ensure_ascii=False, indent=2),
                "implicacoes": json.dumps(implic, ensure_ascii=False, indent=2),
                "janela_show": implic["janela_show"],
            })
            print(f"{UI.OK}Dados carregados e estruturados.{UI.RESET}")

        elif op == "3":
            if "audiencia_struct" not in memoria:
                print(f"{UI.WARN}Nenhum dado estruturado. Use a opção 1 ou 2 primeiro.{UI.RESET}")
                continue
            UI.print_h1("Audiência (Estruturado)")
            print(memoria["audiencia_struct"])
            if UI.ask_yesno("Deseja editar manualmente o JSON?"):
                raw = UI.ask_multiline("Cole o JSON editado", end_token="fim")
                try:
                    aud = json.loads(raw)
                    implic = derivar_implicacoes(aud)
                    memoria.update({
                        "audiencia_struct": json.dumps(aud, ensure_ascii=False, indent=2),
                        "implicacoes": json.dumps(implic, ensure_ascii=False, indent=2),
                        "janela_show": implic["janela_show"],
                    })
                    print(f"{UI.OK}JSON validado e salvo.{UI.RESET}")
                except Exception as e:
                    print(f"{UI.ERR}JSON inválido: {e}{UI.RESET}")

        elif op == "4":
            # Pré-validações
            faltas = [k for k in ("audiencia_struct","implicacoes","janela_show") if k not in memoria]
            if faltas:
                print(f"{UI.WARN}Falta: {', '.join(faltas)}. Insira dados do público antes.{UI.RESET}")
                continue
            if not UI.ask_yesno("Gerar dossiê agora?"):
                continue

            memoria["tema"] = "Espetáculos de Ballet Clássico"
            memoria["funcao"] = ("Gerar dossiê com programa, release, cronograma técnico, "
                                 "alinhados aos dados de público.")
            crew.run()

            UI.print_h1("= Dossiê – Ballet Clássico =")
            for sec, key in [
                ("Programa", "programa_classico"),
                ("Release", "release_press"),
                ("Cronograma Técnico", "cronograma_tecnico"),
                ("Relação entre Dados e Decisões", "relacao_dados_respostas"),
            ]:
                print(f"\n{UI.BOLD}{sec}:{UI.RESET}\n{memoria.get(key,'(vazio)')}\n")

        elif op == "5":
            if "programa_classico" not in memoria:
                print(f"{UI.WARN}Nada para salvar. Gere o dossiê primeiro (opção 4).{UI.RESET}")
                continue
            base = UI.ask("Nome base do arquivo (sem extensão) [dossie_ballet]: ").strip() or "dossie_ballet"
            salvar_md(base + ".md", memoria)
            salvar_json(base + ".json", {
                k: v for k, v in memoria.items()
                if k in ("programa_classico","release_press","cronograma_tecnico",
                         "relacao_dados_respostas","dados_publico","audiencia_struct","implicacoes","janela_show")
            })
            print(f"{UI.OK}Arquivos salvos: {base}.md e {base}.json{UI.RESET}")

        elif op == "6":
            if UI.ask_yesno("Sair agora?"):
                print("Até mais!")
                break
        else:
            print(f"{UI.WARN}Opção inválida.{UI.RESET}")

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    try:
        menu()
    except Exception as e:
        print(f"{UI.ERR}Erro inesperado: {e}{UI.RESET}")
        sys.exit(1)
