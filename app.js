new Vue({
    el: '#app',
    data: {
        apiUrl: '',
        ws: null,
        dragging: false,
        cardPosition: { x: 0, y: 0 },
        offset: { x: 0, y: 0 },
        cardId: 'card1', // Assuming each card has a unique ID
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
            // Update card position based on message
            if (message.cardId === this.cardId && !this.dragging) {
                const card = this.$el.querySelector('.card');
                card.style.left = `${message.x}px`;
                card.style.top = `${message.y}px`;
            }
        },
        dragStart(event) {
            this.dragging = true;
            const card = event.target;
            this.offset.x = event.clientX - card.getBoundingClientRect().left;
            this.offset.y = event.clientY - card.getBoundingClientRect().top;
            document.addEventListener('mousemove', this.dragMove);
            document.addEventListener('mouseup', this.dragEnd);
            // Send message that this client has picked up the card
            this.send({ action: 'pickup', cardId: this.cardId });
        },
        dragMove(event) {
            if (!this.dragging) return;
            const x = event.clientX - this.offset.x;
            const y = event.clientY - this.offset.y;
            this.cardPosition.x = x;
            this.cardPosition.y = y;
            const card = this.$el.querySelector('.card');
            card.style.left = `${x}px`;
            card.style.top = `${y}px`;
            // Send card position update
            this.send({ action: 'move', cardId: this.cardId, x, y });
        },
        dragEnd() {
            this.dragging = false;
            document.removeEventListener('mousemove', this.dragMove);
            document.removeEventListener('mouseup', this.dragEnd);
            // Send message that this client has dropped the card
            this.send({ action: 'drop', cardId: this.cardId, x: this.cardPosition.x, y: this.cardPosition.y });
        }
    }
});
