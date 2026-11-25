using var response = await http.GetAsync({{request_uri}}, HttpCompletionOption.ResponseHeadersRead, ct);
response.EnsureSuccessStatusCode();
var dto = await response.Content.ReadFromJsonAsync<{{dto_type}}>(cancellationToken: ct);
