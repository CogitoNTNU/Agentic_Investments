import numpy as np

class LinearRegression():
    def __init__(self, lr=0.001, n_iterations=1000):
        self.weights = None
        self.bias = None
        
        self.lr = lr
        self.n_iterations = n_iterations
        
        self.loss_history = []
        
    def fit(self, X, y):
        """
        Estimates parameters for the classifier
        
        Args:
            X (array<m,n>): a matrix of floats with
                m rows (#samples) and n columns (#features)
            y (array<m>): a vector of floats
        """
        self.weights = np.zeros(X.shape[1])
        self.bias = 0

        # Gradient Descent 
        for _ in range(self.n_iterations): #iteration = epochs
            lin_model = np.matmul(X, self.weights) + self.bias #y_pred
            loss = np.mean((y-lin_model)**2)
            # compute gradients to update parameters (derived lossfunction)
            # self.weights = self.weights - self.lr * np.dot(X.T , (lin_model - y)) 
            
            self.weights = self.weights - self.lr * np.dot(X.T, (lin_model - y)) / X.shape[0]
            
            self.bias -= self.lr * np.mean(lin_model - y)
            # compute loss
            self.loss_history.append(loss)

        
    
    def predict(self, X):
        """
        Generates predictions
        
        Note: should be called after .fit()
        
        Args:
            X (array<m,n>): a matrix of floats with 
                m rows (#samples) and n columns (#features)
            
        Returns:
            A length m array of floats
        """
        lin_model = np.matmul(X, self.weights) + self.bias
        return lin_model
    

 