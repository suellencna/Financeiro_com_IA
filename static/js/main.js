// Este código é executado quando a página termina de carregar
document.addEventListener('DOMContentLoaded', function() {

    // Adiciona um item inicial em cada container para o usuário já ver os campos
    adicionarItem('receita');
    adicionarItem('desconto');

});

function adicionarItem(tipo) {
    // Encontra o container correto (receitas ou descontos)
    const container = document.getElementById(`${tipo}s-container`);

    // Cria um novo 'div' para agrupar os campos do item
    const itemDiv = document.createElement('div');
    itemDiv.className = 'flex items-center space-x-2 mb-2';

    // Cria o campo de descrição
    const descInput = document.createElement('input');
    descInput.type = 'text';
    descInput.name = `${tipo}_desc[]`; // O '[]' é importante para o Flask receber como uma lista
    descInput.placeholder = 'Descrição';
    descInput.className = 'w-1/2 p-2 border border-gray-300 rounded-md';

    // Cria o campo de valor
    const valorInput = document.createElement('input');
    valorInput.type = 'number';
    valorInput.step = '0.01';
    valorInput.name = `${tipo}_valor[]`; // O '[]' é importante para o Flask receber como uma lista
    valorInput.placeholder = 'Valor (R$)';
    valorInput.className = 'w-1/3 p-2 border border-gray-300 rounded-md';

    // Cria o botão de remover
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.innerText = 'X';
    removeButton.className = 'bg-gray-300 text-gray-700 font-bold py-2 px-3 rounded-md hover:bg-gray-400';
    removeButton.onclick = function() {
        // Quando clicado, remove o 'div' pai que contém os campos e o botão
        container.removeChild(itemDiv);
    };

    // Adiciona os campos e o botão ao 'div' do item
    itemDiv.appendChild(descInput);
    itemDiv.appendChild(valorInput);
    itemDiv.appendChild(removeButton);

    // Adiciona o 'div' do item completo ao container principal
    container.appendChild(itemDiv);
}

// Disponibiliza a função globalmente para ser chamada pelo AlpineJS no HTML
window.adicionarItem = adicionarItem;

