new Vue({
    el: '#app',
    data: {
        apiUrl: 'ws://localhost:6789', // Default WebSocket server URL
        ws: null,
        cards: {}, // Object to store the state of multiple cards
        dragging: false,
        cardPosition: { x: 0, y: 0 },
        offset: { x: 0, y: 0 },
        dragCardId: null, // Store the ID of the card being dragged
    },
    methods: {
        connect() {
            this.ws = new WebSocket(this.apiUrl);
            this.ws.onmessage = this.onMessage;
            this.ws.onopen = () => console.log('Connected to the server');
            this.ws.onerror = (error) => console.log('WebSocket Error: ' + error);
        },
        send(message) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify(message));
            }
        },
        onMessage(event) {
            const message = JSON.parse(event.data);
            if (message.type === 'init') {
                this.cards = message.state.cards;
            } else if (message.type === 'update') {
                this.$set(this.cards, message.cardId, { x: message.x, y: message.y });
            } else if (message.type === 'newCard') {
                this.$set(this.cards, message.cardId, { x: message.x, y: message.y });
                this.creatingCard = false; // Disable creation mode after placing a new card
            }
        },
        createCard() {
            this.creatingCard = !this.creatingCard; // Toggle card creation mode
        },
        gameAreaClick(event) {
            if (this.creatingCard) {
                const x = event.clientX;
                const y = event.clientY;
                this.send({ action: 'createCard', x: x, y: y }); // Request to create a new card at x, y
            }
        },
        dragStart(event, cardId) {
            this.dragging = true;
            this.dragCardId = cardId;
            const cardElement = this.$el.querySelector(`.card[data-card-id="${cardId}"]`);
            this.offset.x = event.clientX - cardElement.getBoundingClientRect().left;
            this.offset.y = event.clientY - cardElement.getBoundingClientRect().top;
            document.addEventListener('mousemove', this.dragMove);
            document.addEventListener('mouseup', this.dragEnd);
            // Send message to the server
            this.send({ action: 'pickup', cardId: this.dragCardId });
        },
        dragMove(event) {
            if (!this.dragging || !this.dragCardId) return;
            const x = event.clientX - this.offset.x;
            const y = event.clientY - this.offset.y;
            // Update the position directly for smooth dragging
            const cardElement = this.$el.querySelector(`.card[data-card-id="${this.dragCardId}"]`);
            if (cardElement) {
                cardElement.style.left = `${x}px`;
                cardElement.style.top = `${y}px`;
            }
            this.send({ action: 'move', cardId: this.dragCardId, x, y });
        },

        dragEnd() {
            this.dragging = false;
            document.removeEventListener('mousemove', this.dragMove);
            document.removeEventListener('mouseup', this.dragEnd);
            if (this.dragCardId) {
                const cardElement = this.$el.querySelector(`.card[data-card-id="${this.dragCardId}"]`);
                const x = parseFloat(cardElement.style.left);
                const y = parseFloat(cardElement.style.top);
                // Notify the server of the card drop and its final position
                this.send({ action: 'drop', cardId: this.dragCardId, x: x, y: y });
                this.dragCardId = null;
            }
        },
    }
});