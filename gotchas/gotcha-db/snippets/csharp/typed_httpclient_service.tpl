public sealed class {{service_name}}(HttpClient http)
{
    public async Task<{{model_type}}?> Get{{operation}}Async(CancellationToken ct = default)
    {
        // TODO(gotcha:fetch): GET the endpoint with cancellation + timeout
        // TODO(gotcha:parse): deserialize the response body
        // TODO(gotcha:map): map DTO -> {{model_type}}
        throw new NotImplementedException();
    }
}
