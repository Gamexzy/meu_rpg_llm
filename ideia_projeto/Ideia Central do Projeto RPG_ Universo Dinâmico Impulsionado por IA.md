# **Ideia Central do Projeto RPG: Universo Dinâmico Impulsionado por IA**

## **1\. Visão Geral: Um RPG de Texto Vivo e em Constante Evolução**

O objetivo fundamental deste projeto é construir um **RPG de texto avançado e dinâmico**, onde o universo de jogo não é estático ou pré-definido em sua totalidade, mas sim **emergente e em constante expansão** com base nas ações do jogador e na inteligência artificial. Buscamos oferecer uma experiência narrativa de alta coesão e consistência, superando as limitações comuns dos LLMs em cenários de longo prazo.

A narrativa não será linear nem baseada em escolhas pré-determinadas. Em vez disso, o jogador terá total liberdade de ação, e o mundo reagirá de forma orgânica e realista, moldando-se às suas decisões.

## **2\. A Arquitetura Fundacional: Os "Três Pilares Vivos"**

Para alcançar esta visão, o projeto adota uma arquitetura de dados híbrida, composta por três bases de dados especializadas, que atuam como a **"fonte da verdade em tempo real"** do universo. A grande inovação é que a lore do mundo não reside mais primariamente em arquivos estáticos (como YAMLs), mas sim **vive e evolui diretamente nestes pilares**:

* **Pilar B: SQLite (O Catálogo Factual)**  
  * **Função:** Armazena o estado factual, estruturado e volátil do jogo. É o "catálogo" de todas as entidades canônicas do universo (locais, personagens, elementos universais, facções) e de todos os dados do jogador (status, inventário, habilidades, conhecimentos, logs).  
  * **Características:** Leve, sem servidor, de alta performance para consultas rápidas e indexadas. É a base onde os novos dados são primeiramente inseridos e de onde os outros pilares são sincronizados. Seu esquema é universal, capaz de descrever mundos de fantasia ou ficção científica através do campo perfil\_json e da metatabela tipos\_entidades.  
* **Pilar C: Neo4j (O Cérebro das Conexões)**  
  * **Função:** Mapeia e consulta as relações complexas e intrínsecas entre todas as entidades do mundo. É o motor que entende a espacialidade (quem está dentro de quem, quem dá acesso a quem) e as interconexões narrativas.  
  * **Características:** Banco de dados de grafos otimizado para travessias complexas e multi-saltos, essencial para navegação, contexto espacial e descoberta de novos caminhos e relações.  
* **Pilar A: ChromaDB (A Memória de Contexto)**  
  * **Função:** Armazena as descrições textuais detalhadas da lore como *embeddings* vetoriais, permitindo buscas por significado semântico (similaridade) para o LLM. É a "memória de longo prazo" do sistema, que permite ao LLM recuperar informações relevantes para a narrativa.  
  * **Características:** Base de dados vetorial otimizada para o pipeline RAG (Geração Aumentada por Recuperação), crucial para mitigar alucinações e fundamentar as respostas da IA em fatos do mundo.

O Orquestrador Central: DataManager  
O DataManager é a única camada que interage diretamente com esses três pilares. Ele atua como um orquestrador central, responsável por direcionar as operações de leitura e escrita para o pilar apropriado e, crucialmente, garantir a consistência e a sincronização dos dados entre eles.

## **3\. População e Expansão Dinâmica do Mundo ("Check-or-Create")**

A essência da visão dinâmica é que o mundo do jogo começa com uma estrutura mínima (ou até vazia), e o conteúdo é adicionado e evoluído durante a jogabilidade, através de um ciclo de "checagem e criação":

* **Início de Campanha Vazio/Mínimo:**  
  * O build\_world.py agora se encarrega apenas de criar o **esquema universal vazio** do banco de dados SQLite (estado.db), incluindo a metatabela tipos\_entidades populada com os tipos básicos de entidades (Locais, Personagens, Elementos Universais, Facções).  
  * A população inicial do mundo (personagem do jogador e sua primeira localização, por exemplo) é feita diretamente pelo DataManager durante a "criação da campanha" (disparada pela UI do aplicativo).  
* **Mecanismo "Check-or-Create":**  
  * Para cada nova entidade (local, item, PNJ, tecnologia, etc.) que o jogo precisa referenciar, o sistema (via DataManager) primeiro **verifica se ela já existe** no banco de dados (get\_entity\_details\_by\_canonical\_id).  
  * **Se existe:** A entidade existente é utilizada, garantindo consistência e evitando duplicação.  
  * **Se não existe:** A entidade é criada dinamicamente (add\_location, add\_element\_universal, etc.) e inserida no banco de dados.  
* **Propostas da IA e Canonização Dinâmica:**  
  * Durante a jogabilidade, o **Agente Mestre de Jogo (MJ)**, impulsionado por um LLM (Google Gemini), pode "descobrir" ou "propor" novas entidades ou alterações na lore.  
  * O "Agente Escriba" (um modo do LLM) gera os dados para essa nova lore em um **formato estruturado (JSON)**.  
  * Após a **aprovação humana** (o "Arquiteto do Mundo" – você), o DataManager executa uma **"Cascata de Canonização"**:  
    1. Insere/atualiza os dados factuais no **SQLite (Pilar B)**.  
    2. Cria ou atualiza os nós e relações correspondentes no **Neo4j (Pilar C)**.  
    3. Gera e armazena os *embeddings* das descrições da nova lore no **ChromaDB (Pilar A)**.  
  * Isso inclui a capacidade de o DataManager **criar dinamicamente novas colunas** em tabelas existentes no SQLite, se a complexidade de uma nova descoberta assim o exigir.

## **4\. O Papel da Inteligência Artificial (LLM)**

O Google Gemini (especialmente versões com grande contexto e capacidade de *Function Calling*) é central para:

* **Geração Narrativa:** Criar descrições ricas e interações realistas com base no contexto do mundo.  
* **Geração de Lore Dinâmica:** Propor novas entidades, relações e atributos de forma estruturada.  
* **Recuperação de Contexto (RAG/GraphRAG):** Utilizar o ChromaDB e o Neo4j para buscar informações relevantes do mundo, garantindo que as respostas da IA sejam precisas e coerentes com a lore canônica.  
* **Interação Estruturada (*Function Calling*):** O LLM pode "chamar" funções do DataManager para obter ou modificar o estado do mundo de forma controlada e segura.

## **5\. O Resultado: Um Universo em Expansão Constante**

Este projeto visa criar um universo de RPG que não é apenas grande, mas **infinitamente expansível**. A lore emerge e se solidifica à medida que o jogo é jogado, permitindo uma imersão profunda e uma experiência verdadeiramente única, onde o jogador e a IA co-criam a história e o mundo. A flexibilidade do esquema universal do SQLite garante que o mesmo motor de jogo possa se adaptar a qualquer gênero ou cenário que a narrativa explorar.