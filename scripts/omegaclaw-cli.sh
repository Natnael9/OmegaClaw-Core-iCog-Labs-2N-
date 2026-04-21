#!/usr/bin/env bash

help() {
    echo -e "Usage: ${0} [command] [options]"
    echo
    echo -e "Commands:"
    echo -e "\tstart start new docker container"
    echo -e "\tstop stop docker container"
    echo -e "\tclean cleanup memory"
    echo
    echo -e "Options:"
    echo -e "\t-s <auth secret> set secret for the communication channel (default is 0000)"
    echo -e "\t-t <api token> set API token"
    echo -e "\t-p <provider> set LLM API provider (default is ASICloud)"
    echo -e "\t-i <IRC channel> set IRC channel"
    echo -e "\t-d <Docker image> set Docker image name (default omegaclaw:latest)"
}

options() {
    OMEGACLAW_AUTH_SECRET=0000
    provider=ASICloud
    image=omegaclaw:latest
    command=${1}
    shift 1

    while getopts s:t:p:c:d: flag
    do
        case "${flag}" in
            s) OMEGACLAW_AUTH_SECRET=${OPTARG};;
            t) api_token=${OPTARG};;
            p) provider=${OPTARG};;
            c) IRC_channel=${OPTARG};;
            d) image=${OPTARG};;
            *) help
               return 1
               ;;
        esac
    done

    case "${provider}" in
        Anthropic)
            embeddingprovider="Local"
            api_token_var="ANTHROPIC_API_KEY"
            ;;
        ASICloud)
            embeddingprovider="Local"
            api_token_var="ASI_API_KEY"
            ;;
        OpenAI)
            embeddingprovider="OpenAI"
            api_token_var="OPENAI_API_KEY"
            ;;
        *) help
           return 1
           ;;
    esac
}

start() {
    docker rm -f omegaclaw 2>/dev/null || true

    docker run -d -it \
        --pull newer \
        --name omegaclaw \
        --user 65534:65534 \
        --security-opt no-new-privileges:true \
        --init \
        --volume omegaclaw-memory:/PeTTa/repos/OmegaClaw-Core/memory \
        --tmpfs /tmp:size=64m,mode=1777 \
        --tmpfs /run:size=16m,mode=755 \
        --tmpfs /var/tmp:size=64m,mode=1777 \
        -e "${api_token_var}"="${api_token}" \
        -e OMEGACLAW_AUTH_SECRET="$OMEGACLAW_AUTH_SECRET" \
        "$image" \
        IRC_channel="$IRC_channel" \
        provider="$provider" \
        embeddingprovider="$embeddingprovider"
}

stop() {
    docker stop omegaclaw
}

cleanup() {
    docker volume rm omegaclaw-memory
}

set -e
options "$@"
case "${command}" in
    start) start ;;
    stop) stop ;;
    cleanup) cleanup ;;
    *) help
       exit 1
       ;;
esac

