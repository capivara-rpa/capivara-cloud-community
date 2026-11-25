const estado = {
  conectores: [],
  conjuntos: [],
  conjuntoAtivo: "Todos",
  workflows: [],
  estatisticas: null,
  credenciais: [],
  modelos: [],
  execucoes: [],
  execucoesAgendadas: [],
  agendamentos: [],
  visaoAgenda: "lista",
  calendarioAgenda: { ano: new Date().getFullYear(), mes: new Date().getMonth() + 1 },
  workflowAtual: null,
  noSelecionado: null,
  execucaoAtual: null,
  editor: null,
  alterado: false,
  carregando: false,
  tema: localStorage.getItem("capivara-cloud-tema") || "claro",
};

let VIEW_ATUAL = "dashboard";
let toastTimer = null;

const TITULOS = {
  dashboard: ["Visão geral", "Seu centro de automação de APIs, em português."],
  fluxos: ["Fluxos", "Monte o fluxo no canvas e configure cada bloco."],
  execucoes: ["Execuções", "Histórico completo com trace por passo."],
  agendamentos: ["Agendamentos", "Disparos automáticos por intervalo, horário ou cron — como na Lagoa."],
  conexoes: ["Conexões", "Conectores prontos e documentação pública."],
  credenciais: ["Credenciais", "Segredos cifrados em repouso com Fernet."],
  api: ["API / Swagger", "Integre por HTTP, webhook ou OpenAPI."],
};

document.addEventListener("DOMContentLoaded", iniciar);

async function iniciar() {
  aplicarTema();
  configurarTema();
  configurarNavegacao();
  configurarEventos();
  inicializarDrawflow();
  await carregarTudo();

  const hash = window.location.hash.replace("#", "");
  trocarView(TITULOS[hash] ? hash : "dashboard", false);

  verificarConexao();
  window.setInterval(verificarConexao, 15000);
  window.setInterval(() => {
    if (VIEW_ATUAL === "dashboard") carregarEstatisticas();
  }, 12000);

  window.addEventListener("resize", () => {
    if (VIEW_ATUAL === "fluxos") estado.editor?.zoom_refresh();
  });
}

function configurarNavegacao() {
  document.querySelectorAll(".nav-link").forEach((botao) => {
    botao.addEventListener("click", () => trocarView(botao.dataset.view));
  });
  window.addEventListener("hashchange", () => {
    const view = window.location.hash.replace("#", "");
    if (TITULOS[view] && view !== VIEW_ATUAL) trocarView(view, false);
  });
}

function configurarTema() {
  document.getElementById("btn-tema").addEventListener("click", () => {
    estado.tema = estado.tema === "escuro" ? "claro" : "escuro";
    localStorage.setItem("capivara-cloud-tema", estado.tema);
    aplicarTema();
  });
}

function aplicarTema() {
  document.documentElement.dataset.tema = estado.tema;
  const escuro = estado.tema === "escuro";
  document.getElementById("tema-icone").textContent = escuro ? "☾" : "☀";
  document.getElementById("tema-texto").textContent = escuro ? "Modo claro" : "Modo escuro";
}

function trocarView(view, atualizarHash = true) {
  if (!TITULOS[view]) return;
  VIEW_ATUAL = view;
  document.querySelectorAll(".view").forEach((secao) => {
    secao.classList.toggle("oculto", secao.id !== `view-${view}`);
  });
  document.querySelectorAll(".nav-link").forEach((botao) => {
    botao.classList.toggle("ativo", botao.dataset.view === view);
  });

  const [titulo, subtitulo] = TITULOS[view];
  document.getElementById("topo-titulo").textContent = titulo;
  document.getElementById("topo-subtitulo").textContent = subtitulo;

  if (atualizarHash) {
    window.history.replaceState(null, "", `#${view}`);
  }

  if (view === "dashboard") renderizarDashboard();
  if (view === "fluxos") {
    renderizarFluxos();
    window.setTimeout(() => estado.editor?.zoom_refresh(), 30);
  }
  if (view === "execucoes") carregarExecucoes();
  if (view === "agendamentos") carregarAgendamentos();
  if (view === "conexoes") renderizarConectores();
  if (view === "credenciais") renderizarCredenciais();
  if (view === "api") renderizarEndpoints();
}

async function carregarTudo() {
  try {
    const [config, conectores, workflows, estatisticas, credenciais, modelos, agendamentos] =
      await Promise.all([
        api("/api/config"),
        api("/api/conectores"),
        api("/api/workflows"),
        api("/api/estatisticas"),
        api("/api/credenciais"),
        api("/api/credenciais/modelos"),
        api("/api/agendamentos"),
      ]);

    estado.conectores = conectores.conectores || [];
    estado.conjuntos = conectores.conjuntos || [];
    estado.workflows = workflows || [];
    estado.estatisticas = estatisticas;
    estado.credenciais = credenciais || [];
    estado.modelos = modelos || [];
    estado.agendamentos = agendamentos || [];

    document.getElementById("versao-app").textContent = `v${config.versao}`;
    document.getElementById("rodape-versao").textContent = `v${config.versao}`;
    document.title = `${config.nome} · Automação de APIs`;

    renderizarPaleta();
    renderizarDashboard();
    renderizarConectores();
    preencherTiposCredencial();
    renderizarListaCredenciais();
    renderizarAgendamentos();
    renderizarEndpoints();
    atualizarStatusWorkflow();
  } catch (erro) {
    console.error(erro);
    toast(`Não foi possível carregar a API: ${erro.message}`, "erro");
  }
}

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    ...opcoes,
    headers: {
      "Content-Type": "application/json",
      ...(opcoes.headers || {}),
    },
  });

  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      detalhe = corpo.detail || corpo.erro || detalhe;
      if (Array.isArray(detalhe)) {
        detalhe = detalhe.map((item) => item.msg || item).join(", ");
      }
    } catch {
      /* resposta sem JSON */
    }
    throw new Error(detalhe);
  }

  if (resposta.status === 204) return null;
  return resposta.json();
}

async function verificarConexao() {
  const caixa = document.getElementById("conexao");
  const texto = document.getElementById("conexao-texto");
  const controlador = new AbortController();
  const timer = window.setTimeout(() => controlador.abort(), 3500);
  try {
    const resposta = await fetch("/api/health", { signal: controlador.signal });
    window.clearTimeout(timer);
    if (!resposta.ok) throw new Error("offline");
    caixa.classList.add("online");
    caixa.classList.remove("offline");
    texto.textContent = "API online";
  } catch {
    window.clearTimeout(timer);
    caixa.classList.add("offline");
    caixa.classList.remove("online");
    texto.textContent = "API offline";
  }
}

function toast(mensagem, tipo = "ok") {
  const elemento = document.getElementById("toast");
  elemento.textContent = mensagem;
  elemento.className = `toast${tipo === "erro" ? " erro" : ""}`;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => elemento.classList.add("oculto"), 4200);
}

function escapar(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (caractere) => {
    const mapa = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return mapa[caractere];
  });
}

function truncar(texto, limite = 42) {
  const valor = String(texto ?? "");
  return valor.length > limite ? `${valor.slice(0, limite - 1)}…` : valor;
}

function formatarData(iso) {
  if (!iso) return "—";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return String(iso).replace("T", " ").slice(0, 19);
  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatarDuracao(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function classeStatus(status) {
  if (status === "concluido") return "concluido";
  if (status === "erro") return "erro";
  return "executando";
}

function rotuloStatus(status) {
  if (status === "concluido") return "concluído";
  if (status === "erro") return "erro";
  return "executando";
}

function classeCategoria(categoria) {
  if (categoria === "Gatilhos") return "gatilho";
  if (categoria === "Lógica") return "logica";
  return "acao";
}

function resumoNo(conector, config) {
  if (config.url) return `${config.metodo || "GET"} ${truncar(config.url, 38)}`;
  if (config.para) return `para ${truncar(config.para, 34)}`;
  if (config.team_id) return `canal ${truncar(config.channel_id || config.team_id, 30)}`;
  if (config.assunto) return truncar(config.assunto, 40);
  if (config.mensagem) return truncar(config.mensagem, 40);
  if (config.texto) return truncar(config.texto, 40);
  if (config.caminho) return truncar(config.caminho, 40);
  if (config.tabela) return `tabela ${truncar(config.tabela, 30)}`;
  if (config.acao) return `${config.acao}${config.nome ? ` · ${truncar(config.nome, 24)}` : ""}`;
  if (config.nome) return truncar(config.nome, 40);
  return truncar(conector.descricao, 42);
}

function logoNo(conector) {
  if (conector.logo) {
    return `<span class="logo-icone" style="--logo:url(${escapar(conector.logo)})"></span>`;
  }
  return `<span class="logo-emoji">${escapar(conector.icone || "◇")}</span>`;
}

function htmlNo(conector, config) {
  return `
    <div class="wf-node wf-${classeCategoria(conector.categoria)}">
      <div class="wf-node-icone">${logoNo(conector)}</div>
      <div class="wf-node-texto">
        <strong>${escapar(conector.nome)}</strong>
        <small>${escapar(resumoNo(conector, config || {}))}</small>
      </div>
      <span class="wf-node-categoria">${escapar(conector.conjunto || conector.categoria)}</span>
    </div>
  `;
}

function configPadrao(conector) {
  const config = {};
  for (const campo of conector.campos || []) {
    config[campo.nome] = campo.padrao ?? "";
  }
  return config;
}

function inicializarDrawflow() {
  estado.editor = new Drawflow(document.getElementById("drawflow"));
  estado.editor.reroute = true;
  estado.editor.start();

  estado.editor.on("nodeSelected", (id) => selecionarNo(id));
  estado.editor.on("nodeUnselected", () => limparInspetor());
  estado.editor.on("nodeCreated", () => marcarAlterado());
  estado.editor.on("nodeMoved", () => marcarAlterado());
  estado.editor.on("nodeRemoved", () => {
    limparInspetor();
    marcarAlterado();
  });
  estado.editor.on("connectionCreated", () => marcarAlterado());
  estado.editor.on("connectionRemoved", () => marcarAlterado());
  estado.editor.on("zoom", (zoom) => {
    document.getElementById("zoom-label").textContent = `${Math.round(zoom * 100)}%`;
  });
}

function marcarAlterado() {
  if (estado.carregando) return;
  estado.alterado = true;
  atualizarStatusWorkflow();
}

function atualizarStatusWorkflow() {
  const chip = document.getElementById("workflow-status");
  const temFluxo = Boolean(estado.workflowAtual);
  if (!temFluxo) {
    chip.textContent = "sem fluxo";
    chip.className = "chip";
  } else if (estado.alterado) {
    chip.textContent = "alterações não salvas";
    chip.className = "chip alterado";
  } else {
    chip.textContent = "salvo";
    chip.className = "chip";
  }
  document.getElementById("btn-salvar").disabled = !temFluxo;
  document.getElementById("btn-executar").disabled = !temFluxo;
  document.getElementById("btn-excluir").disabled = !temFluxo;
}

function renderizarConjuntos() {
  const alvo = document.getElementById("paleta-conjuntos");
  const conjuntos = ["Todos", ...(estado.conjuntos || []).filter((item) => item !== "Todos")];
  alvo.innerHTML = conjuntos
    .map(
      (conjunto) => `
        <button type="button" class="chip-conjunto ${conjunto === estado.conjuntoAtivo ? "ativo" : ""}" data-conjunto="${escapar(conjunto)}">
          ${escapar(conjunto)}
        </button>
      `,
    )
    .join("");
  alvo.querySelectorAll("[data-conjunto]").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.conjuntoAtivo = botao.dataset.conjunto;
      renderizarPaleta();
    });
  });
}

function renderizarPaleta() {
  const lista = document.getElementById("paleta-lista");
  const busca = document.getElementById("busca-paleta").value.trim().toLowerCase();
  renderizarConjuntos();
  const filtrados = estado.conectores.filter((conector) => {
    if (estado.conjuntoAtivo !== "Todos" && conector.conjunto !== estado.conjuntoAtivo) {
      return false;
    }
    const texto = `${conector.nome} ${conector.descricao} ${conector.categoria} ${conector.conjunto}`.toLowerCase();
    return !busca || texto.includes(busca);
  });

  if (!filtrados.length) {
    lista.innerHTML = '<p class="vazio">Nenhum conector encontrado.</p>';
    return;
  }

  const grupos = {};
  for (const conector of filtrados) {
    const grupo = conector.conjunto || conector.categoria;
    if (!grupos[grupo]) grupos[grupo] = [];
    grupos[grupo].push(conector);
  }

  lista.innerHTML = Object.entries(grupos)
    .map(
      ([grupo, conectores]) => `
        <p class="paleta-grupo">${escapar(grupo)}</p>
        ${conectores
          .map(
            (conector) => `
              <div class="paleta-item" draggable="true" data-tipo="${escapar(conector.tipo)}" title="${escapar(conector.descricao)}">
                <span class="paleta-icone">${logoNo(conector)}</span>
                <div>
                  <strong>${escapar(conector.nome)}</strong>
                  <small>${escapar(truncar(conector.descricao, 38))}</small>
                </div>
              </div>
            `,
          )
          .join("")}
      `,
    )
    .join("");
}

function renderizarDashboard() {
  const estatisticas = estado.estatisticas || {};
  const resumo = document.getElementById("resumo");
  const cartoes = [
    ["Fluxos", estatisticas.workflows ?? 0, "prontos para rodar", ""],
    ["Execuções", estatisticas.execucoes ?? 0, "desde o início", "azul"],
    ["Taxa de sucesso", `${estatisticas.taxa_sucesso ?? 0}%`, "das execuções", "amarelo"],
    ["Credenciais", estatisticas.credenciais ?? 0, "cifradas no cofre", "marrom"],
  ];
  resumo.innerHTML = cartoes
    .map(
      ([rotulo, valor, ajuda, classe]) => `
        <div class="resumo-card ${classe}">
          <p class="resumo-rotulo">${escapar(rotulo)}</p>
          <p class="resumo-valor">${escapar(valor)}</p>
          <p class="resumo-ajuda">${escapar(ajuda)}</p>
        </div>
      `,
    )
    .join("");

  const ultimas = estatisticas.ultimas || [];
  const caixaExecucoes = document.getElementById("dashboard-execucoes");
  if (!ultimas.length) {
    caixaExecucoes.innerHTML = '<p class="vazio">Nenhuma execução ainda. Clique em Rodar em um fluxo.</p>';
  } else {
    caixaExecucoes.innerHTML = `<div class="lista-execucoes">${ultimas.map(linhaExecucao).join("")}</div>`;
  }

  const caixaConectores = document.getElementById("dashboard-conectores");
  caixaConectores.innerHTML = estado.conectores
    .slice(0, 6)
    .map(
      (conector) => `
        <div class="conector-mini">
          <span class="conector-mini-icone">${logoNo(conector)}</span>
          <div>
            <strong>${escapar(conector.nome)}</strong>
            <small>${escapar(conector.conjunto || conector.categoria)}</small>
          </div>
        </div>
      `,
    )
    .join("");
}

function linhaExecucao(execucao) {
  const status = execucao.status || "executando";
  return `
    <div class="execucao-linha">
      <div>
        <strong>${escapar(execucao.workflow_nome)}</strong>
        <small>${escapar(formatarData(execucao.inicio))} · ${escapar(execucao.gatilho)}</small>
      </div>
      <div style="align-items:center;display:flex;gap:8px">
        <span class="status status-${classeStatus(status)}">${escapar(rotuloStatus(status))}</span>
        <span class="mono" style="color:var(--texto-3);font-family:var(--fonte-mono);font-size:10px">${escapar(formatarDuracao(execucao.duracao_ms))}</span>
      </div>
    </div>
  `;
}

function renderizarConectores() {
  const total = estado.conectores.length;
  document.getElementById("contador-conectores").textContent = `${total} conectores`;
  const catalogo = document.getElementById("catalogo-conectores");
  if (!total) {
    catalogo.innerHTML = '<p class="vazio">Catálogo indisponível.</p>';
    return;
  }
  catalogo.innerHTML = estado.conectores
    .map((conector) => {
      const credencial = conector.credencial_tipo
        ? `<span class="tag cred">${escapar(conector.credencial_tipo)}</span>`
        : "";
      const docs = conector.docs
        ? `<a class="link" href="${escapar(conector.docs)}" target="_blank" rel="noopener" style="margin-left:auto">Docs ↗</a>`
        : "";
      return `
        <article class="conector-card">
          <div class="conector-card-topo">
            <span class="conector-card-icone">${logoNo(conector)}</span>
            <div>
              <h3>${escapar(conector.nome)}</h3>
              <span class="tag">${escapar(conector.conjunto || conector.categoria)}</span>
            </div>
          </div>
          <p>${escapar(conector.descricao)}</p>
          <div class="conector-card-rodape">
            ${credencial}
            <span class="tag">${conector.entradas ?? 0} in · ${conector.saidas ?? 0} out</span>
            ${docs}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderizarEndpoints() {
  const endpoints = [
    ["GET", "/api/health", "Saúde"],
    ["GET", "/api/conectores", "Catálogo"],
    ["GET", "/api/workflows", "Listar fluxos"],
    ["POST", "/api/workflows", "Criar fluxo"],
    ["PUT", "/api/workflows/{id}", "Atualizar fluxo"],
    ["POST", "/api/workflows/{id}/executar", "Executar"],
    ["POST", "/api/webhooks/{id}", "Webhook"],
    ["GET", "/api/execucoes", "Histórico"],
    ["GET", "/api/credenciais", "Credenciais"],
  ];
  document.getElementById("lista-endpoints").innerHTML = endpoints
    .map(
      ([metodo, caminho, descricao]) => `
        <div class="endpoint">
          <span class="metodo ${metodo.toLowerCase()}">${metodo}</span>
          <code>${escapar(caminho)}</code>
          <span>${escapar(descricao)}</span>
        </div>
      `,
    )
    .join("");

  const id = estado.workflowAtual?.id || "SEU_ID";
  document.getElementById("codigo-webhook").textContent = `curl -X POST ${window.location.origin}/api/webhooks/${id} \\
  -H "Content-Type: application/json" \\
  -d '{"nome":"Arthur","email":"arthur@exemplo.com"}'`;
}

function renderizarFluxos() {
  preencherSeletorWorkflows();
  if (!estado.workflows.length) {
    estado.workflowAtual = null;
    estado.editor.clear();
    limparInspetor();
    atualizarStatusWorkflow();
    return;
  }
  const existe = estado.workflows.some((workflow) => workflow.id === estado.workflowAtual?.id);
  if (!estado.workflowAtual || !existe) {
    carregarWorkflow(estado.workflows[0].id);
    return;
  }
  document.getElementById("seletor-workflow").value = estado.workflowAtual.id;
  atualizarStatusWorkflow();
}

function preencherSeletorWorkflows() {
  const seletor = document.getElementById("seletor-workflow");
  if (!estado.workflows.length) {
    seletor.innerHTML = '<option value="">Nenhum fluxo</option>';
    seletor.disabled = true;
    return;
  }
  seletor.disabled = false;
  seletor.innerHTML = estado.workflows
    .map((workflow) => `<option value="${escapar(workflow.id)}">${escapar(workflow.nome)}</option>`)
    .join("");
  if (estado.workflowAtual) seletor.value = estado.workflowAtual.id;
}

async function carregarWorkflow(id) {
  if (!id) return;
  try {
    const workflow = await api(`/api/workflows/${id}`);
    estado.carregando = true;
    estado.workflowAtual = workflow;
    estado.alterado = false;
    estado.noSelecionado = null;
    estado.editor.clear();
    if (workflow.grafo && Object.keys(workflow.grafo).length) {
      estado.editor.import(workflow.grafo);
    }
    estado.editor.zoom_reset();
    atualizarHtmlDosNos();
    estado.carregando = false;
    limparInspetor();
    preencherSeletorWorkflows();
    atualizarStatusWorkflow();
    renderizarEndpoints();
  } catch (erro) {
    estado.carregando = false;
    toast(erro.message, "erro");
  }
}

async function novoWorkflow() {
  const nome = window.prompt("Nome do novo fluxo:", "Novo fluxo");
  if (!nome || !nome.trim()) return;
  try {
    const workflow = await api("/api/workflows", {
      method: "POST",
      body: JSON.stringify({ nome: nome.trim(), descricao: "", grafo: {} }),
    });
    estado.workflows.unshift(workflow);
    await carregarWorkflow(workflow.id);
    trocarView("fluxos");
    await carregarEstatisticas();
    toast("Fluxo criado.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function salvarWorkflow(silencioso = false) {
  if (!estado.workflowAtual) {
    if (!silencioso) toast("Nenhum fluxo aberto.", "erro");
    return null;
  }
  try {
    const grafo = estado.editor.export();
    const atualizado = await api(`/api/workflows/${estado.workflowAtual.id}`, {
      method: "PUT",
      body: JSON.stringify({ grafo }),
    });
    estado.workflowAtual = atualizado;
    const indice = estado.workflows.findIndex((item) => item.id === atualizado.id);
    if (indice >= 0) estado.workflows[indice] = atualizado;
    estado.alterado = false;
    atualizarStatusWorkflow();
    if (!silencioso) toast("Fluxo salvo.");
    return atualizado;
  } catch (erro) {
    toast(erro.message, "erro");
    return null;
  }
}

async function executarWorkflow() {
  if (!estado.workflowAtual) return;
  const salvo = await salvarWorkflow(true);
  if (!salvo) return;
  try {
    const execucao = await api(`/api/workflows/${salvo.id}/executar`, {
      method: "POST",
      body: JSON.stringify({ entrada: {} }),
    });
    mostrarRun(execucao);
    await carregarEstatisticas();
    if (VIEW_ATUAL === "execucoes") await carregarExecucoes();
    if (execucao.status === "erro") toast(`Execução com erro: ${execucao.erro}`, "erro");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function excluirWorkflow() {
  if (!estado.workflowAtual) return;
  const confirmado = window.confirm(`Excluir o fluxo "${estado.workflowAtual.nome}"?`);
  if (!confirmado) return;
  try {
    await api(`/api/workflows/${estado.workflowAtual.id}`, { method: "DELETE" });
    estado.workflows = estado.workflows.filter((item) => item.id !== estado.workflowAtual.id);
    estado.workflowAtual = null;
    estado.editor.clear();
    limparInspetor();
    if (estado.workflows.length) await carregarWorkflow(estado.workflows[0].id);
    else renderizarFluxos();
    await carregarEstatisticas();
    toast("Fluxo removido.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

function adicionarNo(tipo, x, y) {
  if (!estado.workflowAtual) {
    toast("Crie ou abra um fluxo primeiro.", "erro");
    return;
  }
  const conector = estado.conectores.find((item) => item.tipo === tipo);
  if (!conector) return;
  const config = configPadrao(conector);
  const id = estado.editor.addNode(
    tipo,
    conector.entradas ?? 1,
    conector.saidas ?? 1,
    x,
    y,
    `wf-${classeCategoria(conector.categoria)}`,
    { tipo, nome: conector.nome, config },
    htmlNo(conector, config),
    false,
  );
  marcarAlterado();
  window.setTimeout(() => document.getElementById(`node-${id}`)?.click(), 20);
}

function selecionarNo(id) {
  const no = estado.editor.getNodeFromId(id);
  if (!no) return;
  const conector = estado.conectores.find((item) => item.tipo === no.data.tipo);
  if (!conector) return;
  estado.noSelecionado = String(id);
  renderizarInspetor(no, conector);
}

function limparInspetor() {
  estado.noSelecionado = null;
  document.getElementById("inspetor-vazio").classList.remove("oculto");
  document.getElementById("inspetor-conteudo").classList.add("oculto");
  document.getElementById("inspetor-conteudo").innerHTML = "";
}

function campoVisivel(campo, config) {
  const regras = campo.mostrar_se || {};
  return Object.entries(regras).every(([nome, valores]) => {
    const esperados = (Array.isArray(valores) ? valores : [valores]).map(String);
    return esperados.includes(String(config[nome] ?? ""));
  });
}

function campoControlaOutros(conector, nome) {
  return (conector.campos || []).some(
    (campo) => campo.mostrar_se && Object.prototype.hasOwnProperty.call(campo.mostrar_se, nome),
  );
}

function renderizarInspetor(no, conector) {
  const config = no.data.config || {};
  const campos = (conector.campos || [])
    .filter((campo) => campoVisivel(campo, config))
    .map((campo) => {
      if (campo.tipo === "credencial") return renderizarCredencialNoCampo(campo, conector, config);
      return renderizarCampo(campo, config);
    })
    .join("");

  const docs = conector.docs
    ? `<p class="ajuda">Documentação: <a href="${escapar(conector.docs)}" target="_blank" rel="noopener">abrir ↗</a></p>`
    : "";

  document.getElementById("inspetor-vazio").classList.add("oculto");
  const conteudo = document.getElementById("inspetor-conteudo");
  conteudo.classList.remove("oculto");
  conteudo.innerHTML = `
    <div class="inspetor-cabecalho">
      <span class="chip">${escapar(conector.categoria)}</span>
      <h3>${escapar(conector.nome)}</h3>
      <p>${escapar(conector.descricao)}</p>
      ${docs}
    </div>
    ${campos || '<p class="ajuda">Este nó não tem configuração.</p>'}
    <div class="inspetor-acoes">
      <button class="botao-perigo" id="btn-remover-no" type="button">Remover nó</button>
    </div>
  `;

  conteudo.querySelectorAll("[data-campo]").forEach((elemento) => {
    const evento = elemento.type === "checkbox" || elemento.tagName === "SELECT" ? "change" : "input";
    elemento.addEventListener(evento, () => {
      let valor = elemento.type === "checkbox" ? elemento.checked : elemento.value;
      if (elemento.dataset.tipoCampo === "number" && valor !== "") valor = Number(valor);
      const campo = elemento.dataset.campo;
      atualizarConfigNo(no.id, campo, valor);
      if (campoControlaOutros(conector, campo)) {
        const atualizado = estado.editor.getNodeFromId(no.id);
        if (atualizado) renderizarInspetor(atualizado, conector);
      }
    });
  });

  document.getElementById("btn-remover-no").addEventListener("click", () => {
    if (!window.confirm("Remover este nó do fluxo?")) return;
    estado.editor.removeNodeId(no.id);
    limparInspetor();
    marcarAlterado();
  });
}

function renderizarCampo(campo, config) {
  const valor = config[campo.nome] ?? campo.padrao ?? "";
  const id = `campo-${escapar(campo.nome)}`;
  const obrigatorio = campo.obrigatorio ? " *" : "";
  const ajuda = campo.ajuda ? `<span class="ajuda">${escapar(campo.ajuda)}</span>` : "";
  const base = `id="${id}" data-campo="${escapar(campo.nome)}" data-tipo-campo="${escapar(campo.tipo)}"`;

  if (campo.tipo === "select") {
    const opcoes = (campo.opcoes || [])
      .map(
        (opcao) =>
          `<option value="${escapar(opcao)}" ${String(valor) === String(opcao) ? "selected" : ""}>${escapar(opcao)}</option>`,
      )
      .join("");
    return `<div class="campo"><label for="${id}">${escapar(campo.rotulo)}${obrigatorio}</label><select ${base}>${opcoes}</select>${ajuda}</div>`;
  }

  if (campo.tipo === "textarea" || campo.tipo === "json") {
    return `<div class="campo"><label for="${id}">${escapar(campo.rotulo)}${obrigatorio}</label><textarea ${base} rows="4" placeholder="${escapar(campo.placeholder)}" spellcheck="false">${escapar(valorTexto(valor))}</textarea>${ajuda}</div>`;
  }

  if (campo.tipo === "checkbox") {
    return `<div class="campo campo-check"><input type="checkbox" ${base} ${valor ? "checked" : ""}><label for="${id}">${escapar(campo.rotulo)}${obrigatorio}</label>${ajuda}</div>`;
  }

  const tipoHtml = campo.tipo === "senha" ? "password" : campo.tipo === "number" ? "number" : campo.tipo === "url" ? "url" : campo.tipo === "email" ? "email" : "text";
  return `<div class="campo"><label for="${id}">${escapar(campo.rotulo)}${obrigatorio}</label><input type="${tipoHtml}" ${base} value="${escapar(valorTexto(valor))}" placeholder="${escapar(campo.placeholder)}">${ajuda}</div>`;
}

function renderizarCredencialNoCampo(campo, conector, config) {
  const tipo = conector.credencial_tipo || "";
  const atual = config[campo.nome] || "";
  const opcoes = estado.credenciais.filter((credencial) => credencial.tipo === tipo);
  const htmlOpcoes = opcoes
    .map(
      (credencial) =>
        `<option value="${escapar(credencial.nome)}" ${credencial.nome === atual ? "selected" : ""}>${escapar(credencial.nome)}</option>`,
    )
    .join("");
  const vazio = opcoes.length
    ? ""
    : `<span class="ajuda">Nenhuma credencial do tipo <strong>${escapar(tipo)}</strong>. <button class="link" type="button" data-ir="credenciais">Criar agora</button></span>`;
  return `
    <div class="campo">
      <label for="campo-${escapar(campo.nome)}">${escapar(campo.rotulo)}</label>
      <select id="campo-${escapar(campo.nome)}" data-campo="${escapar(campo.nome)}" data-tipo-campo="credencial">
        <option value="">— sem credencial —</option>
        ${htmlOpcoes}
      </select>
      ${vazio || (campo.ajuda ? `<span class="ajuda">${escapar(campo.ajuda)}</span>` : "")}
    </div>
  `;
}

function valorTexto(valor) {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "object") return JSON.stringify(valor, null, 2);
  return String(valor);
}

function atualizarConfigNo(id, nome, valor) {
  const no = estado.editor.getNodeFromId(id);
  if (!no) return;
  const data = no.data;
  data.config = { ...(data.config || {}), [nome]: valor };
  estado.editor.updateNodeDataFromId(id, data);
  const conector = estado.conectores.find((item) => item.tipo === data.tipo);
  if (!conector) return;
  const html = htmlNo(conector, data.config);
  const modulo = estado.editor.module || "Home";
  const interno = estado.editor.drawflow?.drawflow?.[modulo]?.data?.[id];
  if (interno) interno.html = html;
  const conteudo = document.querySelector(`#node-${id} .drawflow_content_node`);
  if (conteudo) conteudo.innerHTML = html;
  marcarAlterado();
}

function atualizarHtmlDosNos() {
  const modulo = estado.editor.module || "Home";
  const dados = estado.editor.drawflow?.drawflow?.[modulo]?.data || {};
  for (const [id, no] of Object.entries(dados)) {
    const conector = estado.conectores.find((item) => item.tipo === no.data?.tipo);
    if (!conector) continue;
    const html = htmlNo(conector, no.data?.config || {});
    no.html = html;
    const conteudo = document.querySelector(`#node-${id} .drawflow_content_node`);
    if (conteudo) conteudo.innerHTML = html;
  }
}

async function carregarEstatisticas() {
  try {
    estado.estatisticas = await api("/api/estatisticas");
    if (VIEW_ATUAL === "dashboard") renderizarDashboard();
  } catch (erro) {
    console.error(erro);
  }
}

async function carregarExecucoes() {
  try {
    estado.execucoes = await api("/api/execucoes?limite=100");
    renderizarExecucoes();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

function renderizarExecucoes() {
  const corpo = document.getElementById("corpo-execucoes");
  if (!estado.execucoes.length) {
    corpo.innerHTML = '<tr><td colspan="6"><p class="vazio">Nenhuma execução registrada.</p></td></tr>';
    return;
  }
  corpo.innerHTML = estado.execucoes
    .map(
      (execucao) => `
        <tr>
          <td><span class="status status-${classeStatus(execucao.status)}">${escapar(rotuloStatus(execucao.status))}</span></td>
          <td><strong>${escapar(execucao.workflow_nome)}</strong><br><small class="mono">${escapar(execucao.id)}</small></td>
          <td><span class="tag">${escapar(execucao.gatilho)}</span></td>
          <td class="mono">${escapar(formatarData(execucao.inicio))}</td>
          <td class="mono">${escapar(formatarDuracao(execucao.duracao_ms))}</td>
          <td><button class="link" type="button" data-execucao="${escapar(execucao.id)}">Detalhes</button></td>
        </tr>
      `,
    )
    .join("");
}

function mostrarRun(execucao) {
  estado.execucaoAtual = execucao;
  const painel = document.getElementById("run-panel");
  painel.classList.remove("oculto");
  document.getElementById("run-resumo").textContent = `${rotuloStatus(execucao.status)} · ${formatarDuracao(execucao.duracao_ms)} · ${execucao.id}`;
  document.getElementById("run-passos").innerHTML = renderizarTrace(execucao);
}

function renderizarTrace(execucao) {
  if (!execucao.passos || !execucao.passos.length) {
    return '<p class="vazio">Nenhum passo registrado nesta execução.</p>';
  }
  return execucao.passos
    .map((passo) => {
      const status = passo.status === "erro" ? "erro" : "concluido";
      const erro = passo.erro ? `<p class="passo-erro">${escapar(passo.erro)}</p>` : "";
      const detalhe = escapar(JSON.stringify({ entrada: passo.entrada, saida: passo.saida }, null, 2));
      return `
        <div class="passo ${status}">
          <div class="passo-corpo">
            <div class="passo-topo">
              <strong>${escapar(passo.node_nome || passo.tipo)}</strong>
              <span>${escapar(passo.tipo)}</span>
              <span>· ${escapar(formatarDuracao(passo.duracao_ms))}</span>
            </div>
            ${erro}
            <details>
              <summary>Entrada e saída</summary>
              <pre>${detalhe}</pre>
            </details>
          </div>
        </div>
      `;
    })
    .join("");
}

async function abrirExecucao(id) {
  try {
    const execucao = await api(`/api/execucoes/${id}`);
    document.getElementById("dialog-execucao-titulo").textContent = execucao.workflow_nome;
    document.getElementById("dialog-execucao-subtitulo").textContent = `${execucao.id} · ${formatarData(execucao.inicio)} · ${rotuloStatus(execucao.status)}`;
    const erro = execucao.erro ? `<p class="passo-erro">${escapar(execucao.erro)}</p>` : "";
    document.getElementById("dialog-execucao-corpo").innerHTML = `${erro}${renderizarTrace(execucao)}`;
    const dialog = document.getElementById("dialog-execucao");
    if (!dialog.open) dialog.showModal();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

function preencherTiposCredencial() {
  const seletor = document.getElementById("cred-tipo");
  if (!estado.modelos.length) {
    seletor.innerHTML = '<option value="http">http</option>';
    return;
  }
  seletor.innerHTML = estado.modelos
    .map((modelo) => `<option value="${escapar(modelo.tipo)}">${escapar(modelo.tipo)} — ${escapar(modelo.conector)}</option>`)
    .join("");
  atualizarModeloCredencial();
}

function atualizarModeloCredencial() {
  const tipo = document.getElementById("cred-tipo").value;
  const modelo = estado.modelos.find((item) => item.tipo === tipo);
  document.getElementById("cred-dados").value = JSON.stringify(modelo?.modelo || {}, null, 2);
  document.getElementById("cred-ajuda").textContent = modelo
    ? `Modelo do conector ${modelo.conector}.${modelo.docs ? ` Docs: ${modelo.docs}` : ""}`
    : "Informe um objeto JSON com os campos da credencial.";
}

function renderizarCredenciais() {
  preencherTiposCredencial();
  renderizarListaCredenciais();
}

function renderizarListaCredenciais() {
  const caixa = document.getElementById("lista-credenciais");
  if (!estado.credenciais.length) {
    caixa.innerHTML = '<p class="vazio">Nenhuma credencial cadastrada.</p>';
    return;
  }
  caixa.innerHTML = `<div class="lista-credenciais">${estado.credenciais
    .map(
      (credencial) => `
        <div class="credencial-item">
          <div>
            <strong>${escapar(credencial.nome)}</strong>
            <small>${escapar(credencial.tipo)} · ${escapar(credencial.id)}</small>
            <code>${escapar(JSON.stringify(credencial.dados))}</code>
          </div>
          <button type="button" data-remover-cred="${escapar(credencial.id)}" title="Remover credencial">×</button>
        </div>
      `,
    )
    .join("")}</div>`;
}

async function carregarCredenciais() {
  try {
    estado.credenciais = await api("/api/credenciais");
    renderizarListaCredenciais();
    if (estado.noSelecionado) selecionarNo(estado.noSelecionado);
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function removerCredencial(id) {
  const credencial = estado.credenciais.find((item) => item.id === id);
  if (!credencial) return;
  if (!window.confirm(`Remover a credencial "${credencial.nome}"?`)) return;
  try {
    await api(`/api/credenciais/${id}`, { method: "DELETE" });
    await carregarCredenciais();
    toast("Credencial removida.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

const DIAS_SEMANA_AGENDA = ["", "seg", "ter", "qua", "qui", "sex", "sab", "dom"];

function corStatusAgenda(status) {
  if (status === "concluido") return "var(--sucesso)";
  if (status === "erro") return "var(--perigo)";
  return "var(--info)";
}

function preencherWorkflowsAgendamento() {
  const seletor = document.getElementById("agenda-workflow");
  const anterior = seletor.value;
  seletor.innerHTML = estado.workflows.length
    ? estado.workflows
        .map((workflow) => `<option value="${escapar(workflow.id)}">${escapar(workflow.nome)}</option>`)
        .join("")
    : '<option value="">Nenhum fluxo</option>';
  seletor.disabled = !estado.workflows.length;
  if (anterior && estado.workflows.some((workflow) => workflow.id === anterior)) {
    seletor.value = anterior;
  }
}

function atualizarCamposAgendamento() {
  const tipo = document.getElementById("agenda-tipo").value;
  const campos = {
    intervalo: "campo-intervalo",
    diario: "campo-hora",
    cron: "campo-cron",
  };
  Object.entries(campos).forEach(([chave, campo]) => {
    document.getElementById(campo).classList.toggle("oculto", chave !== tipo);
  });
  document.getElementById("campo-dias").classList.toggle("oculto", tipo !== "cron");
  document.getElementById("agenda-intervalo").required = tipo === "intervalo";
  document.getElementById("agenda-hora").required = tipo === "diario";
  document.getElementById("agenda-cron").required = tipo === "cron";
}

function aplicarDiasAgenda() {
  const selecionados = Array.from(document.querySelectorAll("#agenda-dias input:checked"))
    .map((input) => Number(input.value))
    .sort((a, b) => a - b);
  let dia = "*";
  if (selecionados.length === 7) {
    dia = "*";
  } else if (selecionados.length === 5 && selecionados.every((valor) => valor >= 1 && valor <= 5)) {
    dia = "seg-sex";
  } else if (selecionados.length) {
    dia = selecionados.map((valor) => DIAS_SEMANA_AGENDA[valor]).join(",");
  }
  const campo = document.getElementById("agenda-cron");
  const partes = campo.value.trim().split(/\s+/);
  while (partes.length < 5) partes.push("*");
  partes[4] = dia;
  campo.value = partes.slice(0, 5).join(" ");
}

function expressaoAgendamento() {
  const tipo = document.getElementById("agenda-tipo").value;
  if (tipo === "intervalo") return `${Number(document.getElementById("agenda-intervalo").value) || 15}m`;
  if (tipo === "diario") return document.getElementById("agenda-hora").value || "09:00";
  return document.getElementById("agenda-cron").value.trim() || "0 9 * * *";
}

function novoAgendamento() {
  const formulario = document.getElementById("form-agendamento");
  formulario.reset();
  document.getElementById("agenda-intervalo").value = "15";
  document.getElementById("agenda-hora").value = "09:00";
  document.getElementById("agenda-cron").value = "0 9 * * seg-sex";
  document.getElementById("agenda-entrada").value = "{}";
  document.getElementById("agenda-ativo").checked = true;
  atualizarCamposAgendamento();
  preencherWorkflowsAgendamento();
  formulario.classList.remove("oculto");
  document.getElementById("agenda-nome").focus();
}

function aplicarVisaoAgenda() {
  const calendario = estado.visaoAgenda === "calendario";
  document.getElementById("tabela-agendamentos").classList.toggle("oculto", calendario);
  document.getElementById("calendario-agendamentos").classList.toggle("oculto", !calendario);
  document.getElementById("btn-agenda-lista").classList.toggle("ativo", !calendario);
  document.getElementById("btn-agenda-calendario").classList.toggle("ativo", calendario);
  if (calendario) renderizarCalendarioAgendamentos();
}

function mudarVisaoAgenda(visao) {
  estado.visaoAgenda = visao;
  aplicarVisaoAgenda();
}

function mudarMesAgenda(deslocamento) {
  const data = new Date(
    estado.calendarioAgenda.ano,
    estado.calendarioAgenda.mes - 1 + deslocamento,
    1,
  );
  estado.calendarioAgenda = { ano: data.getFullYear(), mes: data.getMonth() + 1 };
  renderizarCalendarioAgendamentos();
}

function irParaHojeAgenda() {
  const hoje = new Date();
  estado.calendarioAgenda = { ano: hoje.getFullYear(), mes: hoje.getMonth() + 1 };
  renderizarCalendarioAgendamentos();
}

function chaveDiaAgenda(data) {
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, "0")}-${String(data.getDate()).padStart(2, "0")}`;
}

function renderizarCalendarioAgendamentos() {
  const { ano, mes } = estado.calendarioAgenda;
  const titulo = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(new Date(ano, mes - 1, 1));
  document.getElementById("cal-agenda-titulo").textContent = titulo.charAt(0).toUpperCase() + titulo.slice(1);
  document.getElementById("cal-agenda-legenda").innerHTML = ["concluido", "erro", "executando"]
    .map(
      (status) =>
        `<span><i style="--cor:${corStatusAgenda(status)}"></i>${escapar(status)}</span>`,
    )
    .join("");

  const porDia = new Map();
  estado.execucoesAgendadas.forEach((execucao) => {
    const chave = String(execucao.inicio || execucao.criado_em || "").slice(0, 10);
    if (!chave) return;
    if (!porDia.has(chave)) porDia.set(chave, []);
    porDia.get(chave).push(execucao);
  });

  const primeiro = new Date(ano, mes - 1, 1);
  const inicio = new Date(primeiro);
  inicio.setDate(1 - ((primeiro.getDay() + 6) % 7));
  const hojeChave = chaveDiaAgenda(new Date());
  let html = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    .map((dia) => `<div class="cal-dia-semana">${dia}</div>`)
    .join("");

  for (let indice = 0; indice < 42; indice += 1) {
    const data = new Date(inicio);
    data.setDate(inicio.getDate() + indice);
    const chave = chaveDiaAgenda(data);
    const eventos = porDia.get(chave) || [];
    const classes = ["cal-dia"];
    if (data.getMonth() !== mes - 1) classes.push("fora");
    if (chave === hojeChave) classes.push("hoje");
    const botoes = eventos
      .slice(0, 3)
      .map((execucao) => {
        const nome = escapar(execucao.workflow_nome || execucao.workflow_id || "Fluxo");
        const status = execucao.status || "concluido";
        const id = escapar(execucao.id);
        return `<button type="button" class="cal-evento" style="--cor:${corStatusAgenda(status)}" data-execucao="${id}" title="#${id} · ${nome}">#${id.slice(0, 6)} ${nome}</button>`;
      })
      .join("");
    const mais = eventos.length > 3 ? `<span class="cal-mais">+${eventos.length - 3}</span>` : "";
    html += `<div class="${classes.join(" ")}"><span class="cal-numero">${data.getDate()}</span>${botoes}${mais}</div>`;
  }
  document.getElementById("cal-agenda-grade").innerHTML = html;
}

function renderizarTabelaAgendamentos() {
  const corpo = document.getElementById("corpo-agendamentos");
  if (!estado.agendamentos.length) {
    corpo.innerHTML = '<tr><td colspan="7" class="vazio">Nenhum agendamento cadastrado.</td></tr>';
    return;
  }
  corpo.innerHTML = estado.agendamentos
    .map((agendamento) => {
      const ativo = agendamento.ativo;
      const id = escapar(agendamento.id);
      const erro = agendamento.ultimo_erro
        ? `<code class="erro">${escapar(agendamento.ultimo_erro)}</code>`
        : "";
      return `
        <tr>
          <td class="mono">#${id.slice(0, 6)}</td>
          <td><strong>${escapar(agendamento.nome)}</strong><br><small>${escapar(agendamento.workflow_nome || agendamento.workflow_id)}</small></td>
          <td><span class="tag">${escapar(agendamento.tipo)}</span><br><code class="mono">${escapar(agendamento.expressao)}</code></td>
          <td class="mono">${formatarData(agendamento.proxima_execucao)}</td>
          <td>${agendamento.execucoes} exec.<br><small class="mono">Última: ${formatarData(agendamento.ultima_execucao)}</small>${erro}</td>
          <td><span class="tag ${ativo ? "ativo" : "pausado"}">${ativo ? "ativo" : "pausado"}</span></td>
          <td class="acoes-tabela">
            <button type="button" class="link" data-agenda-acao="rodar" data-id="${id}">Rodar</button>
            <button type="button" class="link" data-agenda-acao="${ativo ? "pausar" : "ativar"}" data-id="${id}">${ativo ? "Pausar" : "Ativar"}</button>
            <button type="button" class="link" data-agenda-acao="remover" data-id="${id}">Remover</button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderizarAgendamentos() {
  preencherWorkflowsAgendamento();
  renderizarTabelaAgendamentos();
  aplicarVisaoAgenda();
}

async function carregarAgendamentos() {
  try {
    const [agendamentos, execucoes] = await Promise.all([
      api("/api/agendamentos"),
      api("/api/execucoes?limite=200"),
    ]);
    estado.agendamentos = agendamentos || [];
    estado.execucoesAgendadas = (execucoes || []).filter((item) => item.gatilho === "agendado");
    renderizarAgendamentos();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function salvarAgendamento(evento) {
  evento.preventDefault();
  const nome = document.getElementById("agenda-nome").value.trim();
  const workflowId = document.getElementById("agenda-workflow").value;
  if (!workflowId) {
    toast("Crie um fluxo antes de agendar.", "erro");
    return;
  }
  let entrada;
  try {
    entrada = JSON.parse(document.getElementById("agenda-entrada").value || "{}");
  } catch {
    toast("Os dados de entrada precisam ser um JSON válido.", "erro");
    return;
  }
  if (!entrada || Array.isArray(entrada) || typeof entrada !== "object") {
    toast("Os dados de entrada devem ser um objeto JSON.", "erro");
    return;
  }
  try {
    await api("/api/agendamentos", {
      method: "POST",
      body: JSON.stringify({
        nome,
        workflow_id: workflowId,
        tipo: document.getElementById("agenda-tipo").value,
        expressao: expressaoAgendamento(),
        entrada,
        ativo: document.getElementById("agenda-ativo").checked,
      }),
    });
    document.getElementById("form-agendamento").classList.add("oculto");
    await carregarAgendamentos();
    toast("Agendamento salvo.");
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function acionarAgendamento(id, acao) {
  const agendamento = estado.agendamentos.find((item) => item.id === id);
  if (!agendamento) return;
  if (acao === "remover" && !window.confirm(`Remover o agendamento "${agendamento.nome}"?`)) {
    return;
  }
  try {
    if (acao === "rodar") {
      const execucao = await api(`/api/agendamentos/${id}/executar`, { method: "POST" });
      toast(
        execucao.status === "erro"
          ? `Execução com erro: ${execucao.erro || "ver trace"}`
          : "Agendamento executado agora.",
        execucao.status === "erro" ? "erro" : "ok",
      );
    } else if (acao === "pausar" || acao === "ativar") {
      await api(`/api/agendamentos/${id}`, {
        method: "PUT",
        body: JSON.stringify({ ativo: acao === "ativar" }),
      });
      toast(acao === "ativar" ? "Agendamento ativado." : "Agendamento pausado.");
    } else if (acao === "remover") {
      await api(`/api/agendamentos/${id}`, { method: "DELETE" });
      toast("Agendamento removido.");
    }
    await carregarAgendamentos();
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

async function verificarAgendamentosAgora() {
  try {
    const resultado = await api("/api/agendamentos/verificar", { method: "POST" });
    await carregarAgendamentos();
    toast(
      `${resultado.executados} executado(s), ${resultado.erros} erro(s) — ${resultado.verificados} verificado(s).`,
    );
  } catch (erro) {
    toast(erro.message, "erro");
  }
}

function configurarEventos() {
  document.getElementById("btn-hero-novo").addEventListener("click", novoWorkflow);
  document.getElementById("btn-hero-exemplo").addEventListener("click", async () => {
    if (!estado.workflows.length) {
      toast("Nenhum fluxo de exemplo disponível.", "erro");
      return;
    }
    await carregarWorkflow(estado.workflows[0].id);
    trocarView("fluxos");
  });

  document.getElementById("btn-novo-fluxo").addEventListener("click", novoWorkflow);
  document.getElementById("btn-salvar").addEventListener("click", () => salvarWorkflow());
  document.getElementById("btn-executar").addEventListener("click", executarWorkflow);
  document.getElementById("btn-excluir").addEventListener("click", excluirWorkflow);
  document.getElementById("seletor-workflow").addEventListener("change", (evento) => carregarWorkflow(evento.target.value));

  document.getElementById("btn-atualizar-execucoes").addEventListener("click", carregarExecucoes);
  document.getElementById("btn-atualizar-agendamentos").addEventListener("click", carregarAgendamentos);
  document.getElementById("btn-verificar-agendamentos").addEventListener("click", verificarAgendamentosAgora);
  document.getElementById("btn-novo-agendamento").addEventListener("click", novoAgendamento);
  document.getElementById("agenda-cancelar").addEventListener("click", () => {
    document.getElementById("form-agendamento").classList.add("oculto");
  });
  document.getElementById("btn-agenda-lista").addEventListener("click", () => mudarVisaoAgenda("lista"));
  document.getElementById("btn-agenda-calendario").addEventListener("click", () => mudarVisaoAgenda("calendario"));
  document.getElementById("cal-agenda-prev").addEventListener("click", () => mudarMesAgenda(-1));
  document.getElementById("cal-agenda-next").addEventListener("click", () => mudarMesAgenda(1));
  document.getElementById("cal-agenda-hoje").addEventListener("click", irParaHojeAgenda);
  document.getElementById("form-agendamento").addEventListener("submit", salvarAgendamento);
  document.getElementById("agenda-tipo").addEventListener("change", atualizarCamposAgendamento);
  document.querySelectorAll("#agenda-dias input").forEach((input) => {
    input.addEventListener("change", aplicarDiasAgenda);
  });
  document.getElementById("btn-fechar-run").addEventListener("click", () => {
    document.getElementById("run-panel").classList.add("oculto");
  });

  document.getElementById("btn-zoom-in").addEventListener("click", () => estado.editor.zoom_in());
  document.getElementById("btn-zoom-out").addEventListener("click", () => estado.editor.zoom_out());
  document.getElementById("btn-zoom-reset").addEventListener("click", () => estado.editor.zoom_reset());
  document.getElementById("busca-paleta").addEventListener("input", renderizarPaleta);

  const paleta = document.getElementById("paleta-lista");
  paleta.addEventListener("dragstart", (evento) => {
    const item = evento.target.closest(".paleta-item");
    if (!item) return;
    evento.dataTransfer.setData("application/x-capivara", item.dataset.tipo);
    evento.dataTransfer.effectAllowed = "copy";
  });
  paleta.addEventListener("click", (evento) => {
    const item = evento.target.closest(".paleta-item");
    if (!item) return;
    adicionarNo(item.dataset.tipo, 320, 240);
  });

  document.getElementById("form-credencial").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const nome = document.getElementById("cred-nome").value.trim();
    const tipo = document.getElementById("cred-tipo").value;
    let dados;
    try {
      dados = JSON.parse(document.getElementById("cred-dados").value);
    } catch {
      toast("Os dados da credencial precisam ser um JSON válido.", "erro");
      return;
    }
    if (!dados || Array.isArray(dados) || typeof dados !== "object") {
      toast("Os dados devem ser um objeto JSON.", "erro");
      return;
    }
    try {
      await api("/api/credenciais", {
        method: "POST",
        body: JSON.stringify({ nome, tipo, dados }),
      });
      document.getElementById("form-credencial").reset();
      preencherTiposCredencial();
      await carregarCredenciais();
      toast("Credencial salva.");
    } catch (erro) {
      toast(erro.message, "erro");
    }
  });

  document.getElementById("cred-tipo").addEventListener("change", atualizarModeloCredencial);
  document.getElementById("btn-fechar-dialog").addEventListener("click", () => document.getElementById("dialog-execucao").close());
  document.getElementById("dialog-execucao").addEventListener("click", (evento) => {
    if (evento.target === evento.currentTarget) evento.currentTarget.close();
  });

  document.addEventListener("click", (evento) => {
    const ir = evento.target.closest("[data-ir]");
    if (ir) trocarView(ir.dataset.ir);
    const execucao = evento.target.closest("[data-execucao]");
    if (execucao) abrirExecucao(execucao.dataset.execucao);
    const remover = evento.target.closest("[data-remover-cred]");
    if (remover) removerCredencial(remover.dataset.removerCred);
    const agenda = evento.target.closest("[data-agenda-acao]");
    if (agenda) acionarAgendamento(agenda.dataset.id, agenda.dataset.agendaAcao);
  });

  document.addEventListener("keydown", (evento) => {
    if ((evento.metaKey || evento.ctrlKey) && evento.key.toLowerCase() === "s") {
      evento.preventDefault();
      if (VIEW_ATUAL === "fluxos") salvarWorkflow();
    }
    if (evento.key === "Escape") {
      const dialog = document.getElementById("dialog-execucao");
      if (dialog.open) dialog.close();
      document.getElementById("run-panel").classList.add("oculto");
    }
    const digitando = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
    if (!digitando && (evento.key === "Delete" || evento.key === "Backspace") && estado.noSelecionado) {
      evento.preventDefault();
      estado.editor.removeNodeId(estado.noSelecionado);
      limparInspetor();
      marcarAlterado();
    }
  });
}

window.permitirSoltar = function permitirSoltar(evento) {
  evento.preventDefault();
  evento.dataTransfer.dropEffect = "copy";
};

window.soltarNo = function soltarNo(evento) {
  evento.preventDefault();
  const tipo = evento.dataTransfer.getData("application/x-capivara");
  if (!tipo || !estado.editor) return;
  const area = estado.editor.precanvas.getBoundingClientRect();
  const x = (evento.clientX - area.left) / estado.editor.zoom;
  const y = (evento.clientY - area.top) / estado.editor.zoom;
  adicionarNo(tipo, x, y);
};
