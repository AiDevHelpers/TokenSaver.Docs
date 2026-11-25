var docOpts = new JsonDocumentOptions
{
    CommentHandling     = JsonCommentHandling.Skip,
    AllowTrailingCommas = true,
};
{{result_var}} = JsonNode.Parse({{input_var}}, nodeOptions: null, documentOptions: docOpts)
           ?.AsObject() ?? new JsonObject();
