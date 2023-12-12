ARG PYTHON_VERSION=3.11
FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

WORKDIR ${LAMBDA_TASK_ROOT}
COPY function/requirements-lambda.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements-lambda.txt

COPY function/*.py ${LAMBDA_TASK_ROOT}

CMD [ "handler.handle_event" ]