# Sistema de Controle Financeiro Pessoal com IA

## 📖 Sobre o Projeto

Este projeto é uma aplicação web completa para controle financeiro pessoal, desenvolvida em Python com o framework Flask. O objetivo foi criar uma solução robusta e inteligente para substituir o controlo manual feito em planilhas do Excel, oferecendo automação, análise de dados e uma interface moderna e intuitiva.

A aplicação permite ao utilizador registar detalhadamente as suas finanças, separadas em Entradas, Gastos e Investimentos, e visualizar resumos mensais e anuais através de um dashboard interativo. O grande diferencial do projeto é a integração com a **API do Gemini (Google AI)**, que permite a importação e categorização automática de transações a partir de extratos bancários.

Este projeto está a ser desenvolvido de forma iterativa, com novas funcionalidades a serem adicionadas regularmente.

---

## ✨ Funcionalidades Implementadas

Até ao momento, o sistema conta com as seguintes funcionalidades:

* **Lançamentos Detalhados:** Formulários separados para registar Gastos, Entradas (com múltiplos itens, como num contracheque) e Investimentos.
* **Contas Fixas e Recorrentes:** Sistema para registar contas mensais (como aluguel ou internet) uma única vez, com geração automática de lançamentos nos meses seguintes.
* **Gestão Personalizada:** Páginas dedicadas para o utilizador criar, editar e excluir as suas próprias:
    * Categorias de Gasto
    * Tipos de Investimento
    * Formas de Pagamento
    * Contas Bancárias (com saldo inicial)
* **Orçamento Mensal:** Funcionalidade para definir um teto de gastos para cada categoria e acompanhar o progresso em tempo real.
* **Dashboard Interativo:**
    * Resumo financeiro do mês (Receitas, Despesas, Investimentos e Saldo).
    * Gráficos dinâmicos (de pizza e de barras) para visualização de dados.
    * Tabela com todos os gastos do mês, com filtros por categoria.
    * Painel para lançar contas de valor variável (como água e luz).
* **Edição de Lançamentos:** Todos os gastos podem ser editados diretamente a partir do dashboard.
* **🤖 Integração com IA (Google Gemini):**
    * Página para importação de extratos bancários ou de cartão de crédito.
    * A IA analisa o texto, extrai as transações, identifica se é uma entrada ou um gasto, e sugere uma categoria apropriada.
    * Página de revisão para o utilizador confirmar os dados antes de os salvar em lote.

---

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python 3, Flask
* **Banco de Dados:** SQLite
* **Frontend:** HTML5, Tailwind CSS, JavaScript
* **Bibliotecas (Python):** `requests`
* **Bibliotecas (JavaScript):** Alpine.js, Chart.js
* **APIs Externas:** Google Gemini API

---

## 🚀 Como Executar o Projeto

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/suellencna/Financeiro_com_IA.git](https://github.com/suellencna/Financeiro_com_IA.git)
    ```
2.  **Navegue para a pasta do projeto e crie um ambiente virtual:**
    ```bash
    cd Financeiro_com_IA
    python -m venv .venv
    ```
3.  **Ative o ambiente virtual:**
    * Windows: `.venv\Scripts\activate`
    * macOS/Linux: `source .venv/bin/activate`
4.  **Instale as dependências:**
    ```bash
    pip install Flask requests
    ```
5.  **Configure a sua API Key do Google:**
    * Crie uma variável de ambiente chamada `GOOGLE_API_KEY` com a sua chave da API. (Veja as [instruções do PyCharm](https://www.jetbrains.com/help/pycharm/creating-and-editing-run-debug-configurations.html#env-vars) ou do seu sistema operativo).
6.  **Execute a aplicação:**
    ```bash
    python app.py
    ```
7.  Abra o seu navegador e aceda a `http://127.0.0.1:5000`.
