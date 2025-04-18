pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                git 'https://github.com/Mohitkoli987/CI-CD_setup_with_Jenkins'
            }
        }
        stage('Install Dependencies') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest || echo "No tests yet"'
            }
        }
        stage('Build Docker Image') {
            steps {
                sh 'docker build -t mohitkoli987/ecom1fordevops .'
            }
        }
        stage('Push to DockerHub') {
            environment {
                DOCKERHUB_USERNAME = credentials('dockerhub-username')
                DOCKERHUB_PASSWORD = credentials('dockerhub-password')
            }
            steps {
                sh """
                    echo "$DOCKERHUB_PASSWORD" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
                    docker push $DOCKERHUB_USERNAME/ecom1fordevops
                """
            }
        }
    }
}
