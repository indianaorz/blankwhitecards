new Vue({
    el: '#app',
    data: {
        apiUrl: 'ws://localhost:6789', // Default WebSocket server URL
        ws: null,
        cards: {}, // Object to store the state of multiple cards
        dragging: false,
        backgroundDragging: false,
        dragStartPoint: { x: 0, y: 0 },
        scrollPosition: { x: 0, y: 0 },
        cardPosition: { x: 0, y: 0 },
        offset: { x: 0, y: 0 },
        imagePrompt: '', // For storing the user's prompt input

        hand: {}, // Object to store cards in the player's hand
        dragCardId: null, // Store the ID of the card being dragged
    },
    mounted() {
    },
    methods: {


        submitPrompt() {
            if (this.ws && this.ws.readyState === WebSocket.OPEN && this.imagePrompt) {
                const message = { action: 'generateImage', prompt: this.imagePrompt };
                this.ws.send(JSON.stringify(message));
                this.imagePrompt = ''; // Clear the prompt input after sending
            } else {
                console.error('WebSocket is not connected.');
            }
        },





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
            if (message.type === 'drawCards') {
                // Store drawn cards in the hand
                this.hand = message.cards;
            }
            else if (message.type === 'init') {
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
        drawCards() {
            this.send({ action: 'draw' });  // Request to draw 4 cards
        },
        selectCardFromHand(cardId) {
            const selectedCard = this.hand[cardId];
            // Remove the selected card from the hand
            // delete this.hand[cardId];
            this.hand = [];

            // Assume the card's center is at the cursor's position
            // Calculate the card's top-left position based on the card's dimensions
            // Assuming you have a reference to the card dimensions (e.g., cardWidth and cardHeight)
            const cardWidth = 100; // Example card width, adjust as needed
            const cardHeight = 140; // Example card height, adjust as needed
            const initialX = event.clientX - cardWidth / 2;
            const initialY = event.clientY - cardHeight / 2;

            // Send a message to the server to add this card to the global game state with initial positions
            this.send({
                action: 'placeCardFromHand',
                cardId: cardId,
                x: initialX,
                y: initialY
            });

            // Update local state to include this card (the server will also broadcast this, but this is for immediate feedback)
            this.cards[cardId] = { ...selectedCard, x: initialX, y: initialY };

            this.$nextTick(() => {
                this.$forceUpdate();
                // Initiate dragging
                this.dragging = true;
                this.dragCardId = cardId;
                // Since we're assuming the card was clicked at its center for the offset, set offsets to half of card dimensions
                this.offset.x = cardWidth / 2;
                this.offset.y = cardHeight / 2;

                // Manually trigger the dragMove method to position the card under the cursor
                // You might need to wrap this in a requestAnimationFrame or set a short timeout if it doesn't work immediately
                requestAnimationFrame(() => {
                    this.dragMove({ clientX: event.clientX, clientY: event.clientY });
                });

                // Listen for mousemove and mouseup to handle drag and drop
                document.addEventListener('mousemove', this.dragMove);
                document.addEventListener('mouseup', this.dragEnd);
            });
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