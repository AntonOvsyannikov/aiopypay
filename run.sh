case "$1" in
  dev)
    docker-compose -f docker-compose.yml -f docker-compose-dev.yml up --build $2
    ;;

  test)
    docker-compose -f docker-compose-test.yml up --build
    docker-compose -f docker-compose-test.yml down -v
    ;;

  cleanup)
    docker-compose -f docker-compose.yml -f docker-compose-dev.yml down -v
    ;;

  prod)
    docker-compose up --build
    ;;

  *)
    echo "Usage: run.sh {prod|test|dev|cleanup}"

esac
