import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Message.css';

const Message = ({ message, showSources, selectedAssistant }) => {
  const { role, content, sources } = message;

  const prefix = role === 'user'
    ? 'You'
    : (selectedAssistant?.name || 'Assistant');

  return (
    <div className={`msg-row ${role}`}>
      <div className={`msg-bubble ${role}`}>
        <span className="msg-author">{prefix}</span>
        <div className="msg-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
        {showSources && sources && sources.length > 0 && (
          <div className="msg-sources">
            <strong>Sources:</strong> {sources.join(', ')}
          </div>
        )}
      </div>
    </div>
  );
};

export default Message;
